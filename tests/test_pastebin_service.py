import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.models import User, Paste
from server.web.app.services.pastebin_service import PastebinService
from server.web.app.services.analytics_collector import AnalyticsCollector

@pytest.mark.asyncio
async def test_create_paste():
    db_session = AsyncMock(spec=AsyncSession)
    analytics_collector = AsyncMock(spec=AnalyticsCollector)
    service = PastebinService(db_session, analytics_collector)
    
    user = User(id="test_user")
    title = "Test Paste"
    content = "This is a test paste."
    language = "python"
    
    paste = await service.create_paste(user, title, content, language)
    
    assert paste.user_id == user.id
    assert paste.title == title
    assert paste.content == content
    assert paste.language == language

@pytest.mark.asyncio
async def test_get_paste_by_paste_id():
    db_session = AsyncMock(spec=AsyncSession)
    analytics_collector = AsyncMock(spec=AnalyticsCollector)
    service = PastebinService(db_session, analytics_collector)
    
    paste = Paste(paste_id="test_paste")
    db_session.execute.return_value.scalar_one_or_none.return_value = paste
    
    retrieved_paste = await service.get_paste_by_paste_id("test_paste")
    
    assert retrieved_paste == paste