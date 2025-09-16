
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from ..db import get_db
from ..models import UptimeRecord

class UptimeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._is_ai_server_online = True
        self._last_downtime = None

    def is_ai_server_online(self) -> bool:
        # In a real application, this might check a cached value from Redis
        # instead of an in-memory variable.
        return self._is_ai_server_online

    async def record_status(self, service_name: str, is_online: bool, details: str = None):
        """
        Records the status of a service in the database.
        """
        record = UptimeRecord(
            service_name=service_name,
            is_online=is_online,
            details=details
        )
        self.db.add(record)
        await self.db.commit()

        # Update in-memory status for quick checks
        if service_name == "AI Endpoint":
            self._is_ai_server_online = is_online
            if not is_online:
                self._last_downtime = datetime.utcnow()

# Dependency for FastAPI
def get_uptime_service(db: AsyncSession = Depends(get_db)) -> UptimeService:
    return UptimeService(db)
