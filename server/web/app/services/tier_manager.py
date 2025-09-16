"""
Centralized Tier and Permission Management System.

This service is responsible for defining and enforcing tier-based permissions,
quotas, and access to features across the entire platform.
"""
from functools import wraps
from fastapi import Depends, HTTPException, status
from typing import Set, Dict
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User, TierConfiguration, UserTier, UserTierEnum
from ..dependencies import get_current_active_user

from ..models import User, TierConfiguration, UserTierEnum

class TierManager:
    """
    Manages tier-based permissions and features by loading configurations
    into memory for fast access.
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.tier_configs: Dict[UserTierEnum, TierConfiguration] = {}

    async def load_tier_configurations(self):
        """
        Loads all tier configurations from the database. This should be called
        on application startup or when configurations are updated.
        """
        result = await self.db.execute(sa.select(TierConfiguration))
        tiers = result.scalars().all()
        for tier in tiers:
            self.tier_configs[tier.tier] = tier

    async def get_user_tier(self, user: User) -> UserTierEnum:
        """
        Determines the active tier for a given user by checking their active
        subscriptions in the database. Defaults to 'free' if no active tier is found.
        """
        stmt = (
            sa.select(UserTier)
            .where(UserTier.user_id == user.id)
            .where(sa.or_(UserTier.end_date.is_(None), UserTier.end_date > datetime.utcnow()))
            .order_by(sa.desc(UserTier.start_date))  # Get the most recent tier
        )
        result = await self.db.execute(stmt)
        active_tier = result.scalars().first()

        if active_tier:
            return active_tier.tier
        
        # In a more complex system, you might check for a default tier or a guest tier.
        # For now, we default to 'free'.
        return UserTierEnum.free

    def has_permission(self, user_tier: UserTierEnum, permission: str) -> bool:
        """
        Checks if a given tier has a specific permission.
        Permissions are derived from the TierConfiguration model.
        """
        config = self.tier_configs.get(user_tier)
        if not config:
            return False
        return getattr(config, permission, False)

    def get_quota(self, user_tier: UserTierEnum, quota_name: str) -> int:
        """
        Retrieves a specific quota limit for a given tier.
        """
        config = self.tier_configs.get(user_tier)
        if not config:
            return 0
        return getattr(config, quota_name, 0)

# Dependency for FastAPI
async def get_tier_manager(db: AsyncSession = Depends(get_db)) -> TierManager:
    manager = TierManager(db)
    await manager.load_tier_configurations()
    return manager

# Decorator for endpoint permission checking
def requires_permission(permission: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(
            current_user: User = Depends(get_current_active_user),
            tier_manager: TierManager = Depends(get_tier_manager),
            **kwargs
        ):
            user_tier = await tier_manager.get_user_tier(current_user)
            if not tier_manager.has_permission(user_tier, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Your tier '{user_tier.value}' does not have permission for this action."
                )
            # Pass the user object to the decorated function if it expects it
            if 'current_user' in func.__code__.co_varnames:
                kwargs['current_user'] = current_user
            return await func(**kwargs)
        return wrapper
    return decorator
