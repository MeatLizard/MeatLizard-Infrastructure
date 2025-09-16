import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.services.moderation_service import ModerationService
from server.web.app.models import User, Paste

@pytest.mark.asyncio
async def test_scan_content_spam(db_session: AsyncSession):
    """
    Test that the scan_content method correctly identifies spam.
    """
    async for session in db_session:
        # Arrange
        moderation_service = ModerationService(session)
        user = User(display_label="spam_user")
        content = Paste(paste_id="spam-paste", content="This is spam", user=user)
        session.add_all([user, content])
        await session.commit()

        # Act
        await moderation_service.scan_content(content)

        # Assert
        assert content.is_moderated is True
        assert content.meta_data['is_spam'] is True

@pytest.mark.asyncio
async def test_scan_content_malware(db_session: AsyncSession):
    """
    Test that the scan_content method correctly identifies malware.
    """
    async for session in db_session:
        # Arrange
        moderation_service = ModerationService(session)
        user = User(display_label="malware_user")
        content = Paste(paste_id="malware-paste", content="This is malware", user=user)
        session.add_all([user, content])
        await session.commit()

        # Act
        await moderation_service.scan_content(content)

        # Assert
        assert content.is_moderated is True
        assert content.meta_data['is_malware'] is True