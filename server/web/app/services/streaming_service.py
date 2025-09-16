
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import os
import hashlib
import hmac
import time
from fastapi import HTTPException, status

from server.web.app.models import MediaFile, PrivacyLevelEnum
from ..config import settings

class StreamingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_media_file(self, media_id: str) -> MediaFile:
        result = await self.db.execute(select(MediaFile).where(MediaFile.media_id == media_id))
        return result.scalar_one_or_none()

    def generate_signed_url(self, media_id: str, expires_in: int = 3600) -> str:
        expires = int(time.time()) + expires_in
        message = f"{media_id}:{expires}".encode('utf-8')
        signature = hmac.new(settings.SECRET_KEY.encode('utf-8'), message, hashlib.sha256).hexdigest()
        return f"/stream/{media_id}?expires={expires}&signature={signature}"

    def validate_signed_url(self, media_id: str, expires: int, signature: str):
        if int(expires) < time.time():
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="URL has expired.")
            
        message = f"{media_id}:{expires}".encode('utf-8')
        expected_signature = hmac.new(settings.SECRET_KEY.encode('utf-8'), message, hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(expected_signature, signature):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature.")

    def get_stream_response(self, media_file: MediaFile, quality: str = "720p", expires: int = None, signature: str = None):
        if media_file.privacy_level == PrivacyLevelEnum.private:
            if not (expires and signature):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature.")
            self.validate_signed_url(media_file.media_id, expires, signature)

        if quality in media_file.transcoded_files:
            file_path = media_file.transcoded_files[quality]
        else:
            file_path = media_file.storage_path

        if not os.path.exists(file_path):
            return None
            
        return FileResponse(file_path, media_type="video/mp4")
