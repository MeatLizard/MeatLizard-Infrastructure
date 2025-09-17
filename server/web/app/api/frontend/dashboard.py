"""
Dashboard frontend routes.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["frontend"])
templates = Jinja2Templates(directory="server/web/app/templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """User dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})