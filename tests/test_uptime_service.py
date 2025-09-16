
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from server.web.app.services.uptime_service import UptimeService
from server.web.app.models import UptimeRecord

@pytest.mark.asyncio
async def test_record_status(db_session: AsyncSession):
    """
    Test that the record_status method of the UptimeService creates a database record.
    """
    async for session in db_session:
        # Arrange
        uptime_service = UptimeService(session)

        # Act
        await uptime_service.record_status("Test Service", is_online=True)

        # Assert
        result = await session.execute(
            select(UptimeRecord).where(UptimeRecord.service_name == "Test Service")
        )
        record = result.scalar_one_or_none()

        assert record is not None
        assert record.is_online is True
