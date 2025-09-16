import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.models import User, AIChatSession, AIChatMessage
from server.web.app.services.chat_service import ChatService
from server.web.app.services.uptime_service import UptimeService

@pytest.mark.asyncio
async def test_create_chat_session():
    db_session = AsyncMock(spec=AsyncSession)
    uptime_service = AsyncMock(spec=UptimeService)
    service = ChatService(db_session, uptime_service)
    
    user = User(id="test_user")
    system_prompt = "You are a helpful assistant."
    
    session = await service.create_session(user, system_prompt)
    
    assert session.user_id == user.id
    assert session.system_prompt == system_prompt

@pytest.mark.asyncio
async def test_add_message_to_session():
    db_session = AsyncMock(spec=AsyncSession)
    uptime_service = AsyncMock(spec=UptimeService)
    service = ChatService(db_session, uptime_service)
    
    session = AIChatSession(id="test_session")
    role = "user"
    content = "Hello, world!"
    
    message = await service.add_message(session, role, content)
    
    assert message.session_id == session.id
    assert message.role == role
    assert message.content == content