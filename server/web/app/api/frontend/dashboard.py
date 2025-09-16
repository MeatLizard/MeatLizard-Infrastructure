
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from server.web.app.services.reporting_service import ReportingService
from server.web.app.middleware.permissions import get_current_user
from server.web.app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    service: ReportingService = Depends()
):
    dashboard_data = await service.get_user_dashboard(user)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "dashboard_data": dashboard_data}
    )
