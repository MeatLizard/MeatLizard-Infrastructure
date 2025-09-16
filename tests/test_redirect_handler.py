"""
Unit tests for the Redirect Handler service.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from unittest.mock import AsyncMock

from server.web.app.models import User, URLShortener
from server.web.app.services.redirect_handler import RedirectHandler

@pytest.mark.asyncio
async def test_handle_redirect_success(db_session: AsyncSession):
    """
    Tests that a valid slug redirects to the target URL and increments the click count.
    """
    async for session in db_session:
        analytics_mock = AsyncMock()
        handler = RedirectHandler(session, analytics=analytics_mock)
        
        user = User(display_label="test_user")
        short_url = URLShortener(
            slug="test-slug",
            target_url="https://example.com",
            click_count=5
        )
        user.content.append(short_url)
        session.add(user)
        await session.commit()

        target = await handler.handle_redirect("test-slug")

        await session.refresh(short_url) # Refresh to get the updated click count

        assert target == "https://example.com"
        assert short_url.click_count == 6
        analytics_mock.track_event.assert_called_once_with(
            "link_click",
            user=short_url.user,
            content_id=short_url.id
        )
        break

@pytest.mark.asyncio
async def test_handle_redirect_not_found(db_session: AsyncSession):
    """
    Tests that an invalid slug raises a 404 Not Found error.
    """
    async for session in db_session:
        handler = RedirectHandler(session, analytics=AsyncMock())
        
        with pytest.raises(HTTPException) as exc_info:
            await handler.handle_redirect("non-existent-slug")
        
        assert exc_info.value.status_code == 404
        break

@pytest.mark.asyncio
async def test_handle_redirect_inactive_url(db_session: AsyncSession):
    """
    Tests that an inactive URL raises a 404 Not Found error.
    """
    async for session in db_session:
        handler = RedirectHandler(session, analytics=AsyncMock())
        
        user = User(display_label="test_user")
        short_url = URLShortener(
            slug="inactive-slug",
            target_url="https://example.com",
            is_active=False
        )
        user.content.append(short_url)
        session.add(user)
        await session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await handler.handle_redirect("inactive-slug")
        
        assert exc_info.value.status_code == 404
        break
