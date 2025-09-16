
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.pastebin_service import PastebinService
from server.web.app.models import User, PrivacyLevelEnum
from server.web.app.middleware.permissions import get_current_user

router = APIRouter()

class PasteRequest(BaseModel):
    content: str
    title: str = None
    language: str = None
    privacy_level: PrivacyLevelEnum = PrivacyLevelEnum.public
    password: str = None

@router.post("/api/paste")
async def create_paste(
    request: PasteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    service = PastebinService(db)
    paste = await service.create_paste(
        content=request.content,
        user=user,
        title=request.title,
        language=request.language,
        privacy_level=request.privacy_level,
        password=request.password
    )
    return {"paste_id": paste.paste_id}

@router.get("/api/paste/{paste_id}")
async def get_paste(paste_id: str, db: AsyncSession = Depends(get_db)):
    service = PastebinService(db)
    paste = await service.get_paste_by_paste_id(paste_id)
    if not paste:
        raise HTTPException(status_code=404, detail="Paste not found.")
    
    # In a real app, you'd handle privacy checks here
    return {
        "title": paste.title,
        "content": paste.content,
        "language": paste.language,
        "created_at": paste.created_at
    }
