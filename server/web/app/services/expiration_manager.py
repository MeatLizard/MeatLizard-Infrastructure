"""
Service for managing the expiration of pastes and other content.
"""
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy as sa
from datetime import datetime

from ..models import Paste

class ExpirationManager:
    """
    Handles the cleanup of expired content.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def cleanup_expired_pastes(self):
        """
        Finds and deactivates expired pastes.
        
        This is intended to be run as a background job.
        """
        expired_pastes = await self.db.scalars(
            sa.select(Paste).where(
                Paste.is_active == True,
                Paste.expires_at <= datetime.utcnow()
            )
        )
        
        count = 0
        for paste in expired_pastes:
            paste.is_active = False
            count += 1
        
        if count > 0:
            await self.db.commit()
            
        return count