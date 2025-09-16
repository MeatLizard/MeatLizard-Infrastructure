from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from fastapi import Depends, HTTPException, status

from server.web.app.models import AIChatSession, AIChatMessage, User
from .uptime_service import UptimeService, get_uptime_service
from ..db import get_db

class ChatService:
    def __init__(self, db: AsyncSession, uptime_service: UptimeService):
        self.db = db
        self.uptime_service = uptime_service

    async def create_session(self, user: User, system_prompt: str = None) -> AIChatSession:
        if not self.uptime_service.is_ai_server_online():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI server is currently offline.")

        session = AIChatSession(
            user_id=user.id,
            system_prompt=system_prompt
        )
        self.db.add(session)
        await self.db.commit()
        return session

    async def add_message(self, session: AIChatSession, role: str, content: str) -> AIChatMessage:
        if not self.uptime_service.is_ai_server_online():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI server is currently offline.")

        message = AIChatMessage(
            session_id=session.id,
            role=role,
            content=content
        )
        self.db.add(message)
        await self.db.commit()
        return message

    async def get_session_history(self, session_id: UUID) -> list[AIChatMessage]:
        result = await self.db.execute(
            select(AIChatMessage)
            .where(AIChatMessage.session_id == session_id)
            .order_by(AIChatMessage.timestamp)
        )
        return result.scalars().all()

# Dependency for FastAPI
def get_chat_service(
    db: AsyncSession = Depends(get_db),
    uptime_service: UptimeService = Depends(get_uptime_service)
) -> ChatService:
    return ChatService(db, uptime_service)
