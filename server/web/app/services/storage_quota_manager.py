
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from fastapi import Depends

from server.web.app.models import User, MediaFile
from .tier_manager import TierManager, get_tier_manager
from ..db import get_db

class StorageQuotaManager:
    def __init__(self, db: AsyncSession, tier_manager: TierManager):
        self.db = db
        self.tier_manager = tier_manager

    async def get_user_storage_usage(self, user: User) -> int:
        result = await self.db.execute(
            select(func.sum(MediaFile.file_size_bytes)).where(MediaFile.user_id == user.id)
        )
        return result.scalar_one_or_none() or 0

    async def has_sufficient_storage(self, user: User, file_size: int) -> bool:
        user_tier = await self.tier_manager.get_user_tier(user)
        storage_quota_gb = self.tier_manager.get_quota(user_tier, 'storage_quota_gb')
        quota_bytes = storage_quota_gb * (1024 ** 3)
        
        current_usage = await self.get_user_storage_usage(user)
        
        return (current_usage + file_size) <= quota_bytes

# Dependency for FastAPI
def get_storage_quota_manager(
    db: AsyncSession = Depends(get_db),
    tier_manager: TierManager = Depends(get_tier_manager)
) -> StorageQuotaManager:
    return StorageQuotaManager(db, tier_manager)
