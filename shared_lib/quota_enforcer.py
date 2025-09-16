
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime

from server.web.app.models import User, UserTier, UserTierEnum
from shared_lib.tier_manager import tier_manager

class QuotaEnforcer:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def get_user_tier(self, db: AsyncSession, user: User) -> UserTierEnum:
        query = select(UserTier).where(
            UserTier.user_id == user.id,
            UserTier.start_date <= datetime.utcnow(),
            (UserTier.end_date == None) | (UserTier.end_date >= datetime.utcnow())
        ).order_by(UserTier.start_date.desc())
        result = await db.execute(query)
        user_tier_record = result.scalars().first()
        return user_tier_record.tier if user_tier_record else UserTierEnum.free

    async def check_quota(self, db: AsyncSession, user: User, quota_type: str):
        user_tier_enum = await self.get_user_tier(db, user)
        tier_config = tier_manager.get_tier(user_tier_enum)
        
        if not tier_config:
            return False

        quota_limit = getattr(tier_config, f"{quota_type}_quota", 0)
        if quota_limit == 0: # 0 means unlimited
            return True

        usage_key = f"quota:{user.id}:{quota_type}"
        current_usage = await self.redis.get(usage_key)
        current_usage = int(current_usage) if current_usage else 0

        return current_usage < quota_limit

    async def increment_usage(self, user: User, quota_type: str):
        usage_key = f"quota:{user.id}:{quota_type}"
        await self.redis.incr(usage_key)

quota_enforcer: QuotaEnforcer = None

def initialize_quota_enforcer(redis_client: redis.Redis):
    global quota_enforcer
    quota_enforcer = QuotaEnforcer(redis_client)
