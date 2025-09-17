"""
Frontend routes for admin dashboard.
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ...dependencies import get_current_user
from ...models import User

router = APIRouter(prefix="/admin", tags=["admin-frontend"])
templates = Jinja2Templates(directory="server/web/app/templates")


# Dependency to check admin permissions
async def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Ensure the current user has admin permissions."""
    # TODO: Implement proper admin role checking
    # For now, we'll assume all authenticated users are admins
    # In production, this should check for admin role/permissions
    return current_user


@router.get("/videos", response_class=HTMLResponse)
async def admin_video_dashboard(
    request: Request,
    current_user: User = Depends(require_admin_user)
):
    """Serve the admin video management dashboard."""
    return templates.TemplateResponse(
        "admin_video_dashboard.html",
        {"request": request, "user": current_user}
    )


@router.get("/system", response_class=HTMLResponse)
async def admin_system_dashboard(
    request: Request,
    current_user: User = Depends(require_admin_user)
):
    """Serve the admin system configuration dashboard."""
    return templates.TemplateResponse(
        "system_config_dashboard.html",
        {"request": request, "user": current_user}
    )