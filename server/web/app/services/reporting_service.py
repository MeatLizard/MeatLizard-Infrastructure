
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from server.web.app.models import User, AnalyticsEvent, Content, URLShortener, Paste, MediaFile

class ReportingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_dashboard(self, user: User):
        content_stats = await self.db.execute(
            select(
                Content.content_type,
                func.count(Content.id)
            )
            .where(Content.user_id == user.id)
            .group_by(Content.content_type)
        )

        url_clicks = await self.db.scalar(
            select(func.sum(URLShortener.click_count))
            .where(URLShortener.user_id == user.id)
        )

        paste_views = await self.db.scalar(
            select(func.sum(Paste.view_count))
            .where(Paste.user_id == user.id)
        )

        return {
            "content_stats": dict(content_stats.all()),
            "url_clicks": url_clicks or 0,
            "paste_views": paste_views or 0,
        }

    async def get_admin_dashboard(self):
        result = await self.db.execute(
            select(
                AnalyticsEvent.event_type,
                func.count(AnalyticsEvent.id)
            )
            .group_by(AnalyticsEvent.event_type)
        )
        return result.all()
