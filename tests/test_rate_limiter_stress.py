
import pytest
import asyncio
from fastapi import FastAPI, Depends, Request
from httpx import AsyncClient
import redis.asyncio as redis
from uuid import uuid4

from server.web.app.services.rate_limiter import rate_limit_dependency, get_redis
from server.web.app.models import User, UserTierEnum
from server.web.app.services.tier_manager import TierManager, get_tier_manager
from server.web.app.dependencies import get_current_active_user

# --- Mock Dependencies ---

# Mock user for testing
mock_user = User(id=uuid4(), display_label="test_user")

async def override_get_current_active_user() -> User:
    return mock_user

async def override_get_tier_manager() -> TierManager:
    # Create a mock TierManager that returns a fixed rate limit
    mock_manager = TierManager(db_session=None) # No DB needed for this test
    mock_manager.get_user_tier = asyncio.coroutine(lambda user: UserTierEnum.free)
    mock_manager.get_quota = lambda tier, quota_name: 10 if quota_name == 'rate_limit_per_minute' else 0
    return mock_manager

# --- Test FastAPI App ---

app = FastAPI()

@app.get("/test-rate-limit")
async def test_endpoint(limit: bool = Depends(rate_limit_dependency)):
    return {"status": "ok"}

# Override dependencies in the test app
app.dependency_overrides[Depends(get_current_active_user)] = override_get_current_active_user
app.dependency_overrides[Depends(get_tier_manager)] = override_get_tier_manager

# --- The Test ---

@pytest.mark.asyncio
async def test_rate_limiter_burst():
    """
    Sends a burst of requests to a protected endpoint to ensure the
    rate limiter correctly blocks requests that exceed the limit.
    """
    # Connect to a real Redis for this integration test
    redis_client = redis.Redis(host="localhost", port=6379, db=1, decode_responses=True)
    
    # Clean up any old keys before the test
    user_key = f"rate_limit:user:{mock_user.id}"
    await redis_client.delete(user_key)

    # Override the get_redis dependency to use our test client
    async def override_get_redis(request: Request) -> redis.Redis:
        return redis_client
    
    app.dependency_overrides[Depends(get_redis)] = override_get_redis

    rate_limit = 10
    request_count = 15

    async with AsyncClient(app=app, base_url="http://test") as client:
        tasks = [client.get("/test-rate-limit") for _ in range(request_count)]
        responses = await asyncio.gather(*tasks)

    success_responses = [r for r in responses if r.status_code == 200]
    rate_limited_responses = [r for r in responses if r.status_code == 429]

    assert len(success_responses) == rate_limit
    assert len(rate_limited_responses) == request_count - rate_limit

    # Clean up after the test
    await redis_client.delete(user_key)
    await redis_client.close()
