import pytest
from unittest.mock import AsyncMock, MagicMock
import time

from server.web.app.models import User, TierConfiguration, UserTierEnum
from shared_lib.rate_limiter import RateLimiter
from shared_lib.tier_manager import tier_manager

@pytest.mark.asyncio
async def test_rate_limiter_allows_requests_within_limit():
    redis_client = AsyncMock()
    rate_limiter = RateLimiter(redis_client)
    
    user = User(id="test_user")
    tier_manager.tiers = {
        UserTierEnum.free: TierConfiguration(tier=UserTierEnum.free, display_name="Free", rate_limit_per_minute=10)
    }
    
    request = MagicMock()
    request.client.host = "127.0.0.1"

    # Mock Redis zcard to return a count below the limit
    redis_client.zcard.return_value = 5

    assert not await rate_limiter.is_rate_limited(user, request)

@pytest.mark.asyncio
async def test_rate_limiter_blocks_requests_over_limit():
    redis_client = AsyncMock()
    rate_limiter = RateLimiter(redis_client)
    
    user = User(id="test_user")
    tier_manager.tiers = {
        UserTierEnum.free: TierConfiguration(tier=UserTierEnum.free, display_name="Free", rate_limit_per_minute=10)
    }
    
    request = MagicMock()
    request.client.host = "127.0.0.1"

    # Mock Redis zcard to return a count above the limit
    redis_client.zcard.return_value = 15

    assert await rate_limiter.is_rate_limited(user, request)