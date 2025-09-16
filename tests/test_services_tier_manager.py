import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.services.tier_manager import TierManager
from server.web.app.models import User, UserTier, TierConfiguration, UserTierEnum

@pytest.mark.asyncio
async def test_get_user_tier_with_no_tier(db_session: AsyncSession):
    """
    Test that a user with no tier entry defaults to the 'free' tier.
    """
    async for session in db_session:
        # Arrange
        user = User(display_label="test_user")
        session.add(user)
        await session.commit()

        tier_manager = TierManager(session)
        await tier_manager.load_tier_configurations()

        # Act
        user_tier = await tier_manager.get_user_tier(user)

        # Assert
        assert user_tier == UserTierEnum.free

@pytest.mark.asyncio
async def test_get_user_tier_with_expired_tier(db_session: AsyncSession):
    """
    Test that a user with an expired tier defaults to the 'free' tier.
    """
    async for session in db_session:
        # Arrange
        user = User(display_label="expired_user")
        vip_config = TierConfiguration(tier=UserTierEnum.vip, display_name="VIP")
        expired_tier = UserTier(
            user=user,
            tier=UserTierEnum.vip,
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow() - timedelta(days=1)
        )
        session.add_all([user, vip_config, expired_tier])
        await session.commit()

        tier_manager = TierManager(session)
        await tier_manager.load_tier_configurations()

        # Act
        user_tier = await tier_manager.get_user_tier(user)

        # Assert
        assert user_tier == UserTierEnum.free

@pytest.mark.asyncio
async def test_get_user_tier_with_active_tier(db_session: AsyncSession):
    """
    Test that the correct tier is returned for a user with an active tier.
    """
    async for session in db_session:
        # Arrange
        user = User(display_label="active_user")
        vip_config = TierConfiguration(tier=UserTierEnum.vip, display_name="VIP")
        active_tier = UserTier(
            user=user,
            tier=UserTierEnum.vip,
            start_date=datetime.utcnow() - timedelta(days=15),
            end_date=datetime.utcnow() + timedelta(days=15)
        )
        session.add_all([user, vip_config, active_tier])
        await session.commit()

        tier_manager = TierManager(session)
        await tier_manager.load_tier_configurations()

        # Act
        user_tier = await tier_manager.get_user_tier(user)

        # Assert
        assert user_tier == UserTierEnum.vip

@pytest.mark.asyncio
async def test_get_user_tier_with_permanent_tier(db_session: AsyncSession):
    """
    Test that a tier with no end date is considered active.
    """
    async for session in db_session:
        # Arrange
        user = User(display_label="permanent_user")
        business_config = TierConfiguration(tier=UserTierEnum.business, display_name="Business")
        permanent_tier = UserTier(
            user=user,
            tier=UserTierEnum.business,
            start_date=datetime.utcnow() - timedelta(days=100),
            end_date=None  # Permanent tier
        )
        session.add_all([user, business_config, permanent_tier])
        await session.commit()

        tier_manager = TierManager(session)
        await tier_manager.load_tier_configurations()

        # Act
        user_tier = await tier_manager.get_user_tier(user)

        # Assert
        assert user_tier == UserTierEnum.business

@pytest.mark.asyncio
async def test_get_user_tier_selects_most_recent_active(db_session: AsyncSession):
    """
    Test that if a user has multiple active tiers (e.g., an old one and a new one),
    the most recently started one is selected.
    """
    async for session in db_session:
        # Arrange
        user = User(display_label="multi_tier_user")
        vip_config = TierConfiguration(tier=UserTierEnum.vip, display_name="VIP")
        business_config = TierConfiguration(tier=UserTierEnum.business, display_name="Business")
        
        old_vip_tier = UserTier(
            user=user,
            tier=UserTierEnum.vip,
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow() + timedelta(days=30)
        )
        
        # This is the newest, so it should be picked
        new_business_tier = UserTier(
            user=user,
            tier=UserTierEnum.business,
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow() + timedelta(days=365)
        )
        
        session.add_all([user, vip_config, business_config, old_vip_tier, new_business_tier])
        await session.commit()

        tier_manager = TierManager(session)
        await tier_manager.load_tier_configurations()

        # Act
        user_tier = await tier_manager.get_user_tier(user)

        # Assert
        assert user_tier == UserTierEnum.business