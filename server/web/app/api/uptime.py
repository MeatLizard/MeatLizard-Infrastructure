
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.uptime_service import UptimeService

router = APIRouter()

@router.post("/api/uptime/ping/{service_name}")
async def uptime_ping(service_name: str, db: AsyncSession = Depends(get_db)):
    service = UptimeService(db)
    await service.record_uptime_ping(service_name)
    return {"status": "ok"}

@router.get("/api/uptime/stats/{service_name}")
async def get_uptime_stats(service_name: str, db: AsyncSession = Depends(get_db)):
    service = UptimeService(db)
    stats = await service.get_uptime_stats(service_name)
    return stats
