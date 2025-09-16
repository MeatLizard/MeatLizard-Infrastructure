"""
Unit tests for the Quota Enforcer service.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from server.web.app.models import User, MediaFile
from server.web.app.services.quota_enforcer import QuotaEnforcer
from server.web.app.services.tier_manager import TierManager

@pytest.mark.asyncio
async def test_quota_enforcer_logic(db_session: AsyncSession):
    """
    Tests the core logic of the QuotaEnforcer.
    """
    async for session in db_session:
        tier_manager_mock = AsyncMock(spec=TierManager)
        tier_manager_mock.get_user_tier.return_value = "free"
        tier_manager_mock.get_quota.return_value = 1 # 1 GB

        manager = QuotaEnforcer(session, tier_manager_mock)
        
        user = User(display_label="test_user")
        
        # Simulate existing usage
        media_files = [
            MediaFile(user_id=user.id, media_id="1", original_filename="a.mp4", mime_type="video/mp4", storage_path="/a.mp4", file_size_bytes=500 * (1024**2)), # 500 MB
            MediaFile(user_id=user.id, media_id="2", original_filename="b.mp4", mime_type="video/mp4", storage_path="/b.mp4", file_size_bytes=200 * (1024**2)), # 200 MB
        ]
        user.content.extend(media_files)
        session.add(user)
        await session.commit()

        # Test storage check
        await manager.check_storage_quota(user, 300 * (1024**2)) # Should pass
        
        with pytest.raises(Exception):
            await manager.check_storage_quota(user, 400 * (1024**2)) # Should fail
        
        break
