
import random
import string
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import Depends, HTTPException, status

from server.web.app.models import Paste, User, PrivacyLevelEnum
from shared_lib.security import get_password_hash
from .analytics_collector import AnalyticsCollector, get_analytics_collector
from ..db import get_db

class PastebinService:
    def __init__(self, db: AsyncSession, analytics: AnalyticsCollector):
        self.db = db
        self.analytics = analytics

    async def create_paste(
        self,
        content: str,
        user: User,
        title: str = None,
        language: str = None,
        privacy_level: PrivacyLevelEnum = PrivacyLevelEnum.public,
        password: str = None,
        expires_at: datetime = None,
        max_views: int = None
    ) -> Paste:
        paste_id = await self._generate_unique_paste_id()
        
        password_hash = None
        if privacy_level == PrivacyLevelEnum.password and password:
            password_hash = get_password_hash(password)

        paste = Paste(
            paste_id=paste_id,
            title=title,
            content=content,
            language=language,
            privacy_level=privacy_level,
            password_hash=password_hash,
            user_id=user.id,
            expires_at=expires_at,
            max_views=max_views
        )
        self.db.add(paste)
        await self.db.commit()
        return paste

    async def get_paste_by_paste_id(self, paste_id: str) -> Paste:
        paste = await self.db.scalar(select(Paste).where(Paste.paste_id == paste_id))
        
        if not paste or not paste.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paste not found.")

        # Check for expiration
        if paste.expires_at and paste.expires_at < datetime.utcnow():
            paste.is_active = False
            self.db.add(paste)
            await self.db.commit()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paste has expired.")

        if paste.max_views is not None and paste.view_count >= paste.max_views:
            paste.is_active = False
            self.db.add(paste)
            await self.db.commit()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paste has reached its view limit.")
            
        # Atomically increment the view count
        paste.view_count += 1
        self.db.add(paste)
        await self.db.commit()

        # Track the view event
        await self.analytics.track_event(
            "paste_view",
            user=paste.user,
            content_id=paste.id
        )
            
        return paste

    async def _generate_unique_paste_id(self, length: int = 7) -> str:
        while True:
            paste_id = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
            if await self._is_paste_id_available(paste_id):
                return paste_id

    async def _is_paste_id_available(self, paste_id: str) -> bool:
        result = await self.db.execute(select(Paste).where(Paste.paste_id == paste_id))
        return result.scalar_one_or_none() is None

# Dependency for FastAPI
def get_pastebin_service(
    db: AsyncSession = Depends(get_db),
    analytics: AnalyticsCollector = Depends(get_analytics_collector)
) -> PastebinService:
    return PastebinService(db, analytics)
