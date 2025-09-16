
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from server.web.app.services.reporting_service import ReportingService

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/trending", response_class=HTMLResponse)
async def get_trending_content(
    request: Request,
    service: ReportingService = Depends()
):
    trending_data = await service.get_admin_dashboard() # Reusing this for now
    return templates.TemplateResponse(
        "trending.html",
        {"request": request, "trending_data": trending_data}
    )
