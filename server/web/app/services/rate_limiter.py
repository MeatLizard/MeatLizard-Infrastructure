"""
Redis-backed Rate Limiting Service.

Implements a sliding window algorithm to enforce per-user and per-IP rate limits.
"""
import time
from fastapi import Depends, HTTPException, status, Request
from redis.asyncio import Redis

from ..dependencies import get_current_active_user
from ..models import User
from .tier_manager import TierManager, get_tier_manager

# Placeholder for a Redis connection dependency
async def get_redis(request: Request) -> Redis:
    """Provides a Redis connection from the app's connection pool."""
    return Redis(connection_pool=request.app.state.redis_pool)

class RateLimiter:
    """
    A sliding window rate limiter that uses Redis to track request counts.
    """

    def __init__(self, redis: Redis, tier_manager: TierManager):
        self.redis = redis
        self.tier_manager = tier_manager

    async def is_rate_limited(self, key: str, limit: int, window_seconds: int) -> bool:
        """
        Checks if a given key has exceeded the rate limit using a sliding window
        algorithm with a Redis pipeline for atomic operations.

        :param key: The unique identifier for the user or IP.
        :param limit: The number of requests allowed in the window.
        :param window_seconds: The time window in seconds.
        :return: True if the key is rate-limited, False otherwise.
        """
        now = time.time()
        window_start = now - window_seconds

        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window_seconds)
            results = await pipe.execute()

        request_count = results[2]
        return request_count > limit

async def rate_limit_dependency(
    request: Request,
    user: User = Depends(get_current_active_user),
    redis: Redis = Depends(get_redis),
    tier_manager: TierManager = Depends(get_tier_manager)
):
    """
    FastAPI dependency that enforces rate limiting on an endpoint.
    """
    user_tier = await tier_manager.get_user_tier(user)
    rate_limit_per_minute = tier_manager.get_quota(user_tier, 'rate_limit_per_minute')

    # Per-user rate limit
    user_key = f"rate_limit:user:{user.id}"
    if await RateLimiter(redis, tier_manager).is_rate_limited(user_key, rate_limit_per_minute, 60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="User rate limit exceeded."
        )

    # Per-IP rate limit ( stricter, for unauthenticated or abusive traffic)
    ip = request.client.host
    ip_key = f"rate_limit:ip:{ip}"
    # A default, lower limit for all IPs
    if await RateLimiter(redis, tier_manager).is_rate_limited(ip_key, 20, 60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="IP rate limit exceeded."
        )
