import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from server.web.app.services.storage_quota_manager import StorageQuotaManager
from server.web.app.services.tier_manager import TierManager
from server.web.app.models import User, MediaFile, UserTierEnum

@pytest.mark.asyncio
async def test_has_sufficient_storage(db_session: AsyncSession):
    """
    Test the has_sufficient_storage method with various scenarios.
    """
    async for session in db_session:
        # Arrange
        user = User(display_label="storage_user")
        session.add(user)
        await session.commit()

        # Mock the TierManager
        tier_manager_mock = AsyncMock(spec=TierManager)
        tier_manager_mock.get_user_tier.return_value = UserTierEnum.free
        tier_manager_mock.get_quota.return_value = 1  # 1 GB

        storage_quota_manager = StorageQuotaManager(session, tier_manager_mock)

        # Scenario 1: User has no files, upload should be allowed
        assert await storage_quota_manager.has_sufficient_storage(user, 500 * (1024 ** 2)) is True

        # Scenario 2: User has some files, upload should be allowed
        media_file = MediaFile(
            media_id="storage-test-1",
            original_filename="test.mp4",
            file_size_bytes=500 * (1024 ** 2),  # 500 MB
            mime_type="video/mp4",
            storage_path="/test.mp4",
            user=user
        )
        session.add(media_file)
        await session.commit()

        assert await storage_quota_manager.has_sufficient_storage(user, 500 * (1024 ** 2)) is True

        # Scenario 3: User has some files, upload should be denied
        assert await storage_quota_manager.has_sufficient_storage(user, 600 * (1024 ** 2)) is False