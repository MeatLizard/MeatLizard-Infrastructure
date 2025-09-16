import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.services.admin_dashboard_service import AdminDashboardService

@pytest.mark.asyncio
async def test_get_system_health():
    db_session = AsyncMock(spec=AsyncSession)
    service = AdminDashboardService(db_session)
    
    health = await service.get_system_health()
    
    assert health["status"] == "ok"

@pytest.mark.asyncio
async def test_get_user_stats():
    db_session = AsyncMock(spec=AsyncSession)
    service = AdminDashboardService(db_session)
    
    # Mock the database result
    db_session.execute.return_value.scalar_one = AsyncMock(return_value=100)
    
    stats = await service.get_user_stats()
    
    assert stats["total_users"] == 100