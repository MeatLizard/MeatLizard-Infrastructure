
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from fastapi import HTTPException

from server.web.app.services.pastebin_service import PastebinService
from server.web.app.services.analytics_collector import AnalyticsCollector
from server.web.app.models import User, Paste, AnalyticsEvent

@pytest.mark.asyncio
async def test_get_paste_creates_analytics_event(db_session: AsyncSession):
    """
    Test that calling get_paste_by_paste_id creates a 'paste_view' analytics event.
    """
    async for session in db_session:
        # Arrange
        user = User(display_label="analytics_user")
        paste = Paste(
            paste_id="analytics-test-paste",
            content="Some content",
            user=user  # Associate the user directly
        )
        session.add(paste)
        await session.commit()

        analytics_collector = AnalyticsCollector(session)
        pastebin_service = PastebinService(session, analytics_collector)

        # Act
        retrieved_paste = await pastebin_service.get_paste_by_paste_id("analytics-test-paste")

        # Assert
        assert retrieved_paste is not None
        assert retrieved_paste.view_count == 1

        # Verify that the analytics event was created
        result = await session.execute(
            select(AnalyticsEvent).where(AnalyticsEvent.event_type == "paste_view")
        )
        event = result.scalar_one_or_none()

        assert event is not None
        assert event.content_id == retrieved_paste.id
        assert event.user_id == user.id

@pytest.mark.asyncio
async def test_paste_expires_after_time(db_session: AsyncSession):
    """
    Test that a paste with an expiration date becomes inactive after the date has passed.
    """
    async for session in db_session:
        # Arrange
        user = User(display_label="expiring_user")
        paste = Paste(
            paste_id="expiring-paste",
            content="This paste will expire.",
            user=user,
            expires_at=datetime.utcnow() - timedelta(days=1)  # Expired yesterday
        )
        session.add(paste)
        await session.commit()

        analytics_collector = AnalyticsCollector(session)
        pastebin_service = PastebinService(session, analytics_collector)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await pastebin_service.get_paste_by_paste_id("expiring-paste")
        
        assert exc_info.value.status_code == 404
        assert "expired" in exc_info.value.detail.lower()

@pytest.mark.asyncio
async def test_paste_expires_after_max_views(db_session: AsyncSession):
    """
    Test that a paste with a max_views limit becomes inactive after the limit is reached.
    """
    async for session in db_session:
        # Arrange
        user = User(display_label="max_views_user")
        paste = Paste(
            paste_id="max-views-paste",
            content="This paste has a view limit.",
            user=user,
            max_views=2
        )
        session.add(paste)
        await session.commit()

        analytics_collector = AnalyticsCollector(session)
        pastebin_service = PastebinService(session, analytics_collector)

        # Act
        # First two views should succeed
        await pastebin_service.get_paste_by_paste_id("max-views-paste")
        await pastebin_service.get_paste_by_paste_id("max-views-paste")

        # The third view should fail
        with pytest.raises(HTTPException) as exc_info:
            await pastebin_service.get_paste_by_paste_id("max-views-paste")
        
        assert exc_info.value.status_code == 404
        assert "view limit" in exc_info.value.detail.lower()
