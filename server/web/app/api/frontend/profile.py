
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from server.web.app.services.profile_service import ProfileService
from server.web.app.middleware.permissions import get_current_user
from server.web.app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/profile/{user_id}", response_class=HTMLResponse)
async def get_profile(
    request: Request,
    user_id: str,
    service: ProfileService = Depends()
):
    profile_data = await service.get_user_profile(user_id)
    return templates.TemplateResponse(
        "profile.html",
        {"request": request, "profile_data": profile_data}
    )
