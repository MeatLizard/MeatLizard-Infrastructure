
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.leaderboard_service import LeaderboardService

router = APIRouter()

@router.get("/api/leaderboard/{leaderboard_name}")
async def get_leaderboard(leaderboard_name: str, db: AsyncSession = Depends(get_db)):
    service = LeaderboardService(db)
    leaderboard = await service.get_leaderboard(leaderboard_name)
    return leaderboard
