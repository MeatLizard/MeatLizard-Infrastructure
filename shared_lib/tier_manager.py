
from sqlalchemy.ext.asyncio import AsyncSession
from server.web.app.models import TierConfiguration, UserTierEnum

class TierManager:
    def __init__(self):
        self.tiers = {}

    async def load_tiers_from_db(self, db: AsyncSession):
        result = await db.execute(select(TierConfiguration))
        for tier in result.scalars().all():
            self.tiers[tier.tier] = tier

    def get_tier(self, tier_enum: UserTierEnum) -> TierConfiguration:
        return self.tiers.get(tier_enum)

    def get_permission(self, tier_enum: UserTierEnum, permission: str):
        tier = self.get_tier(tier_enum)
        if not tier:
            return None
        return getattr(tier, permission, None)

tier_manager = TierManager()
