
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.reporting_service import ReportingService
from server.web.app.models import User
from server.web.app.middleware.permissions import get_current_user

router = APIRouter()

@router.get("/api/reporting/user")
async def get_user_dashboard(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    service = ReportingService(db)
    dashboard = await service.get_user_dashboard(user)
    return dashboard

@router.get("/api/reporting/admin")
async def get_admin_dashboard(db: AsyncSession = Depends(get_db)):
    # In a real app, you would add an admin permission check here
    service = ReportingService(db)
    dashboard = await service.get_admin_dashboard()
    return dashboard
