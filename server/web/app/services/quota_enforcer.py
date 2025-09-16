"""
Service for enforcing tier-based usage quotas.

This service works with the TierManager to track and enforce limits
on resources like storage, API calls, and other features.
"""
from fastapi import Depends, HTTPException, status
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User, MediaFile
from .tier_manager import TierManager, get_tier_manager

class QuotaEnforcer:
    """
    Tracks and enforces usage quotas for users.
    """

    def __init__(self, db: AsyncSession, tier_manager: TierManager):
        self.db = db
        self.tier_manager = tier_manager

    async def get_current_storage_usage(self, user: User) -> int:
        """Calculates the user's total storage usage in bytes."""
        result = await self.db.execute(
            sa.select(sa.func.sum(MediaFile.file_size_bytes))
            .where(MediaFile.user_id == user.id)
        )
        usage = result.scalar_one()
        return usage or 0

    async def check_storage_quota(self, user: User, file_size_bytes: int):
        """
        Checks if a user has enough storage quota for a new file.
        
        Raises HTTPException if the quota is exceeded.
        """
        user_tier = await self.tier_manager.get_user_tier(user)
        storage_quota_gb = self.tier_manager.get_quota(user_tier, 'storage_quota_gb')
        storage_quota_bytes = storage_quota_gb * (1024 ** 3)

        current_usage_bytes = await self.get_current_storage_usage(user)

        if current_usage_bytes + file_size_bytes > storage_quota_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Storage quota exceeded. Your tier allows {storage_quota_gb} GB."
            )

    async def check_rate_limit(self, user: User):
        """
        Checks if a user has exceeded their API rate limit.

        TODO: This should be implemented with a Redis-backed sliding window
        algorithm for production-grade rate limiting.
        """
        user_tier = await self.tier_manager.get_user_tier(user)
        rate_limit = self.tier_manager.get_quota(user_tier, 'rate_limit_per_minute')
        
        # This is a simplified placeholder and does not enforce any limits.
        pass

# Dependency for FastAPI
def get_quota_enforcer(
    db: AsyncSession = Depends(get_db),
    tier_manager: TierManager = Depends(get_tier_manager)
) -> QuotaEnforcer:
    return QuotaEnforcer(db, tier_manager)
