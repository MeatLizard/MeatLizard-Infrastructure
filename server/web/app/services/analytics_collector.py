"""
Service for collecting and storing analytics events.
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional

from ..db import get_db
from ..models import AnalyticsEvent, User, ContentTypeEnum

class AnalyticsCollector:
    """
    Handles the creation and storage of analytics events.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def track_event(
        self,
        event_type: str,
        user: Optional[User] = None,
        content_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None
    ):
        """
        Creates and stores a new analytics event.

        :param event_type: The type of event (e.g., 'link_click', 'paste_view').
        :param user: The user associated with the event.
        :param content_id: The ID of the content associated with the event.
        :param data: A dictionary of additional event data.
        """
        event = AnalyticsEvent(
            event_type=event_type,
            user_id=user.id if user else None,
            content_id=content_id,
            data=data or {}
        )
        self.db.add(event)
        await self.db.commit()

# Dependency for FastAPI
def get_analytics_collector(db: AsyncSession = Depends(get_db)) -> AnalyticsCollector:
    return AnalyticsCollector(db)
