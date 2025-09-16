"""
Service for handling URL shortener redirections and statistics.
"""
from datetime import datetime
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy as sa

from ..db import get_db
from ..models import URLShortener, User
from .analytics_collector import AnalyticsCollector, get_analytics_collector

class RedirectHandler:
    """
    Handles the logic for redirecting short URLs and tracking clicks.
    """

    def __init__(self, db: AsyncSession, analytics: AnalyticsCollector):
        self.db = db
        self.analytics = analytics

    async def handle_redirect(self, slug: str) -> str:
        """
        Finds a short URL by its slug, checks for expiration, tracks the click,
        and returns the target URL.

        :param slug: The slug of the short URL.
        :return: The target URL for redirection.
        """
        short_url = await self.db.scalar(
            sa.select(URLShortener).where(URLShortener.slug == slug)
        )

        if not short_url or not short_url.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL not found.")

        # Check for expiration
        if short_url.expires_at and short_url.expires_at < datetime.utcnow():
            short_url.is_active = False
            self.db.add(short_url)
            await self.db.commit()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL has expired.")

        if short_url.max_clicks is not None and short_url.click_count >= short_url.max_clicks:
            short_url.is_active = False
            self.db.add(short_url)
            await self.db.commit()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL has reached its click limit.")

        # Atomically increment the click count
        short_url.click_count += 1
        self.db.add(short_url)
        await self.db.commit()

        # Track the click event
        await self.analytics.track_event(
            "link_click",
            user=short_url.user,
            content_id=short_url.id
        )

        return short_url.target_url

# Dependency for FastAPI
def get_redirect_handler(
    db: AsyncSession = Depends(get_db),
    analytics: AnalyticsCollector = Depends(get_analytics_collector)
) -> RedirectHandler:
    return RedirectHandler(db, analytics)
