from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.media_upload_service import MediaUploadService
from server.web.app.models import User
from server.web.app.middleware.permissions import get_current_user

router = APIRouter()

@router.post("/api/media/upload")
async def upload_media(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    service = MediaUploadService(db)
    try:
        media_file = await service.upload_file(file, user)
        return {"media_id": media_file.media_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))