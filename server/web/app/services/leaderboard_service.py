
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from server.web.app.models import LeaderboardEntry, User, URLShortener, Paste

class LeaderboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_leaderboard(self, leaderboard_name: str, limit: int = 10):
        result = await self.db.execute(
            select(LeaderboardEntry)
            .where(LeaderboardEntry.leaderboard_name == leaderboard_name)
            .order_by(LeaderboardEntry.rank)
            .limit(limit)
        )
        return result.scalars().all()

    async def generate_top_users_by_reputation(self, limit: int = 10):
        result = await self.db.execute(
            select(User)
            .order_by(User.reputation_score.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def generate_top_users_by_xp(self, limit: int = 10):
        result = await self.db.execute(
            select(User)
            .order_by(User.experience_points.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def generate_top_urls_by_clicks(self, limit: int = 10):
        result = await self.db.execute(
            select(URLShortener)
            .order_by(URLShortener.click_count.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def generate_top_pastes_by_views(self, limit: int = 10):
        result = await self.db.execute(
            select(Paste)
            .order_by(Paste.view_count.desc())
            .limit(limit)
        )
        return result.scalars().all()
