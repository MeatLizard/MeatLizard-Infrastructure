
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from server.web.app.models import User, Content, AnalyticsEvent

class AdminDashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_system_health(self):
        # In a real app, you would check the status of various services
        # like the database, Redis, Celery, etc.
        return {"status": "ok"}

    async def get_user_stats(self):
        result = await self.db.execute(select(func.count(User.id)))
        return {"total_users": result.scalar_one()}

    async def get_content_stats(self):
        result = await self.db.execute(
            select(
                Content.content_type,
                func.count(Content.id)
            )
            .group_by(Content.content_type)
        )
        return result.all()

    async def get_usage_trends(self):
        result = await self.db.execute(
            select(
                func.date(AnalyticsEvent.timestamp),
                func.count(AnalyticsEvent.id)
            )
            .group_by(func.date(AnalyticsEvent.timestamp))
            .order_by(func.date(AnalyticsEvent.timestamp))
        )
        return result.all()
