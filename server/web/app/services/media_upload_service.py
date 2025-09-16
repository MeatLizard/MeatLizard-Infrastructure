
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile, Depends
import aiofiles
import os
from uuid import uuid4

from server.web.app.models import User, MediaFile
from server.web.app.services.storage_quota_manager import StorageQuotaManager, get_storage_quota_manager
from server.web.app.services.file_validator import FileValidator, get_file_validator
from server.web.app.services.ai_media_service import AIMediaService, get_ai_media_service
from server.background_worker import transcode_media_file
from ..db import get_db
from ..config import settings

class MediaUploadService:
    def __init__(
        self,
        db: AsyncSession,
        quota_manager: StorageQuotaManager,
        file_validator: FileValidator,
        ai_media_service: AIMediaService,
        storage_path: str = settings.MEDIA_STORAGE_PATH
    ):
        self.db = db
        self.quota_manager = quota_manager
        self.file_validator = file_validator
        self.ai_media_service = ai_media_service
        self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)

    async def upload_file(self, file: UploadFile, user: User) -> MediaFile:
        self.file_validator.validate(file)

        if not await self.quota_manager.has_sufficient_storage(user, file.size):
            raise ValueError("Insufficient storage quota.")

        # Generate a unique filename to prevent collisions
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid4()}{file_extension}"
        file_path = os.path.join(self.storage_path, unique_filename)

        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)

        media_file = MediaFile(
            media_id=unique_filename,
            original_filename=file.filename,
            file_size_bytes=file.size,
            mime_type=file.content_type,
            storage_path=file_path,
            user_id=user.id
        )
        self.db.add(media_file)
        await self.db.commit()
        
        # Generate captions
        captions = self.ai_media_service.generate_captions(media_file)
        media_file.captions = captions
        self.db.add(media_file)
        await self.db.commit()

        transcode_media_file.delay(media_file.id)
        
        return media_file

# Dependency for FastAPI
def get_media_upload_service(
    db: AsyncSession = Depends(get_db),
    quota_manager: StorageQuotaManager = Depends(get_storage_quota_manager),
    file_validator: FileValidator = Depends(get_file_validator),
    ai_media_service: AIMediaService = Depends(get_ai_media_service)
) -> MediaUploadService:
    return MediaUploadService(db, quota_manager, file_validator, ai_media_service)
