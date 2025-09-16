
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from server.web.app.db import get_db
from server.web.app.services.chat_service import ChatService
from server.web.app.models import User
from server.web.app.middleware.permissions import get_current_user

router = APIRouter()

class ChatSessionRequest(BaseModel):
    system_prompt: str = None

class ChatMessageRequest(BaseModel):
    session_id: UUID
    content: str

@router.post("/api/chat/session")
async def create_chat_session(
    request: ChatSessionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    service = ChatService(db)
    session = await service.create_session(user, request.system_prompt)
    return {"session_id": session.id}

@router.post("/api/chat/message")
async def add_chat_message(
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    service = ChatService(db)
    
    # In a real app, you would get the session and verify ownership
    session = await db.get(AIChatSession, request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Add user message
    await service.add_message(session, "user", request.content)
    
    # In a real app, you would call the AI service here
    ai_response = "This is a mock AI response."
    
    # Add AI message
    ai_message = await service.add_message(session, "assistant", ai_response)
    
    return {"response": ai_message.content}
