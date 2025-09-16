
import time
import redis.asyncio as redis
from fastapi import Request, HTTPException

from server.web.app.models import User
from shared_lib.tier_manager import tier_manager

class RateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def is_rate_limited(self, user: User, request: Request):
        user_tier_enum = getattr(user, 'tier', 'free')
        tier_config = tier_manager.get_tier(user_tier_enum)
        
        if not tier_config:
            # Default to a safe limit if tier config is missing
            limit = 10
            window = 60
        else:
            limit = tier_config.rate_limit_per_minute
            window = 60

        # Per-user rate limiting
        user_key = f"rate_limit:user:{user.id}"
        if await self._check_limit(user_key, limit, window):
            return True

        # Per-IP rate limiting
        ip = request.client.host
        ip_key = f"rate_limit:ip:{ip}"
        if await self._check_limit(ip_key, limit, window):
            return True

        return False

    async def _check_limit(self, key: str, limit: int, window: int):
        current_time = time.time()
        
        # Remove old entries from the sorted set
        await self.redis.zremrangebyscore(key, 0, current_time - window)
        
        # Add the current request timestamp
        await self.redis.zadd(key, {str(current_time): current_time})
        
        # Get the number of requests in the window
        request_count = await self.redis.zcard(key)
        
        return request_count > limit

rate_limiter: RateLimiter = None

def initialize_rate_limiter(redis_client: redis.Redis):
    global rate_limiter
    rate_limiter = RateLimiter(redis_client)
