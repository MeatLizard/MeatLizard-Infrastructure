"""
Core service for the URL Shortener.

Handles slug generation, validation, and management of short URLs.
"""
import secrets
import string
from datetime import datetime
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy as sa
from urllib.parse import urlparse

from ..db import get_db
from ..models import URLShortener, User
from .analytics_collector import AnalyticsCollector, get_analytics_collector

class URLShortenerService:
    """
    Provides core functionality for the URL shortener.
    """

    def __init__(self, db: AsyncSession, analytics: AnalyticsCollector):
        self.db = db
        self.analytics = analytics

    def generate_slug(self, length: int = 6) -> str:
        """Generates a random, URL-safe slug."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    async def create_short_url(
        self,
        target_url: str,
        user: User,
        custom_slug: str = None,
        expires_at: datetime = None,
        max_clicks: int = None
    ) -> URLShortener:
        """
        Creates a new short URL.

        :param target_url: The URL to shorten.
        :param user: The user creating the URL.
        :param custom_slug: An optional custom slug.
        :param expires_at: An optional expiration date.
        :param max_clicks: An optional maximum number of clicks.
        :return: The newly created URLShortener object.
        """
        # Validate the target URL to prevent open redirects
        parsed_url = urlparse(target_url)
        if not (parsed_url.scheme and parsed_url.netloc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid target URL provided."
            )

        if custom_slug:
            # Check if the custom slug is already in use
            existing = await self.db.scalar(
                sa.select(URLShortener).where(URLShortener.slug == custom_slug)
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Custom slug is already in use."
                )
            slug = custom_slug
        else:
            # Generate a unique random slug
            while True:
                slug = self.generate_slug()
                existing = await self.db.scalar(
                    sa.select(URLShortener).where(URLShortener.slug == slug)
                )
                if not existing:
                    break
        
        short_url = URLShortener(
            target_url=target_url,
            slug=slug,
            user_id=user.id,
            expires_at=expires_at,
            max_clicks=max_clicks
        )
        self.db.add(short_url)
        await self.db.commit()
        
        await self.analytics.track_event("url_created", user=user, content_id=short_url.id)
        
        return short_url

# Dependency for FastAPI
def get_url_shortener_service(
    db: AsyncSession = Depends(get_db),
    analytics: AnalyticsCollector = Depends(get_analytics_collector)
) -> URLShortenerService:
    return URLShortenerService(db, analytics)
