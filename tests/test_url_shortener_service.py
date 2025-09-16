
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.models import User, URLShortener
from server.web.app.services.url_shortener import URLShortenerService

@pytest.mark.asyncio
async def test_create_short_url_with_custom_slug():
    db_session = AsyncMock(spec=AsyncSession)
    service = URLShortenerService(db_session)
    
    user = User(id="test_user")
    target_url = "https://example.com"
    custom_slug = "my-custom-slug"

    # Mock the slug availability check
    service._is_slug_available = AsyncMock(return_value=True)
    
    short_url = await service.create_short_url(target_url, user, custom_slug)
    
    assert short_url.slug == custom_slug
    assert short_url.target_url == target_url
    assert short_url.user_id == user.id

@pytest.mark.asyncio
async def test_create_short_url_with_generated_slug():
    db_session = AsyncMock(spec=AsyncSession)
    service = URLShortenerService(db_session)
    
    user = User(id="test_user")
    target_url = "https://example.com"

    # Mock the slug generation and availability check
    service._generate_unique_slug = AsyncMock(return_value="random-slug")
    
    short_url = await service.create_short_url(target_url, user)
    
    assert short_url.slug == "random-slug"
    assert short_url.target_url == target_url
    assert short_url.user_id == user.id

@pytest.mark.asyncio
async def test_create_short_url_with_unavailable_custom_slug():
    db_session = AsyncMock(spec=AsyncSession)
    service = URLShortenerService(db_session)
    
    user = User(id="test_user")
    target_url = "https://example.com"
    custom_slug = "my-custom-slug"

    # Mock the slug availability check
    service._is_slug_available = AsyncMock(return_value=False)
    
    with pytest.raises(ValueError):
        await service.create_short_url(target_url, user, custom_slug)
