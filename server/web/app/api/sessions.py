from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from uuid import UUID
from ..db import get_db
from ..models import User, AIChatSession

router = APIRouter(prefix="/sessions", tags=["sessions"])

class CreateSessionRequest(BaseModel):
    user_label: str = Field(..., example="WebAppUser_123")

class SessionResponse(BaseModel):
    session_id: UUID

@router.post("/", response_model=SessionResponse, status_code=201)
async def create_web_session(payload: CreateSessionRequest, db: AsyncSession = Depends(get_db)):
    # Simple get/create user logic for web sessions
    user = await db.scalar(select(User).where(User.display_label == payload.user_label))
    if not user:
        user = User(display_label=payload.user_label)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    new_session = AIChatSession(user_id=user.id)
    db.add(new_session)
    await db.commit()

    return {"session_id": new_session.id}
