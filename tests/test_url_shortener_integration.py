
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from server.web.app.services.url_shortener_service import URLShortenerService
from server.web.app.services.redirect_handler import RedirectHandler
from server.web.app.services.analytics_collector import AnalyticsCollector
from server.web.app.models import User, URLShortener

@pytest.mark.asyncio
async def test_url_expires_after_time(db_session: AsyncSession):
    """
    Test that a URL with an expiration date becomes inactive after the date has passed.
    """
    async for session in db_session:
        # Arrange
        user = User(display_label="expiring_user")
        session.add(user)
        await session.commit()

        analytics_collector = AnalyticsCollector(session)
        url_shortener_service = URLShortenerService(session, analytics_collector)
        redirect_handler = RedirectHandler(session, analytics_collector)

        short_url = await url_shortener_service.create_short_url(
            target_url="https://example.com",
            user=user,
            expires_at=datetime.utcnow() - timedelta(days=1)  # Expired yesterday
        )

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await redirect_handler.handle_redirect(short_url.slug)
        
        assert exc_info.value.status_code == 404
        assert "expired" in exc_info.value.detail.lower()

@pytest.mark.asyncio
async def test_url_expires_after_max_clicks(db_session: AsyncSession):
    """
    Test that a URL with a max_clicks limit becomes inactive after the limit is reached.
    """
    async for session in db_session:
        # Arrange
        user = User(display_label="max_clicks_user")
        session.add(user)
        await session.commit()

        analytics_collector = AnalyticsCollector(session)
        url_shortener_service = URLShortenerService(session, analytics_collector)
        redirect_handler = RedirectHandler(session, analytics_collector)

        short_url = await url_shortener_service.create_short_url(
            target_url="https://example.com",
            user=user,
            max_clicks=2
        )

        # Act
        # First two redirects should succeed
        await redirect_handler.handle_redirect(short_url.slug)
        await redirect_handler.handle_redirect(short_url.slug)

        # The third redirect should fail
        with pytest.raises(HTTPException) as exc_info:
            await redirect_handler.handle_redirect(short_url.slug)
        
        assert exc_info.value.status_code == 404
        assert "click limit" in exc_info.value.detail.lower()
