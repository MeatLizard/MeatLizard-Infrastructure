from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.social_service import SocialService
from server.web.app.models import User, Content
from server.web.app.middleware.permissions import get_current_user

router = APIRouter()

class CommentRequest(BaseModel):
    content_id: str
    text: str

class ReactionRequest(BaseModel):
    content_id: str
    reaction_type: str

@router.post("/api/social/comment")
async def add_comment(
    request: CommentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    service = SocialService(db)
    content = await db.get(Content, request.content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found.")
        
    comment = await service.add_comment(content, user, request.text)
    return {"comment_id": comment.id}

@router.post("/api/social/react")
async def add_reaction(
    request: ReactionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    service = SocialService(db)
    content = await db.get(Content, request.content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found.")
        
    reaction = await service.add_reaction(content, user, request.reaction_type)
    return {"reaction_id": reaction.id}