
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from server.web.app.services.pastebin_service import PastebinService
from server.web.app.middleware.permissions import get_current_user
from server.web.app.models import User, PrivacyLevelEnum

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/paste", response_class=HTMLResponse)
async def get_paste_form(request: Request):
    return templates.TemplateResponse("paste.html", {"request": request})

@router.post("/paste", response_class=HTMLResponse)
async def create_paste(
    request: Request,
    content: str,
    title: str = None,
    language: str = None,
    privacy_level: PrivacyLevelEnum = PrivacyLevelEnum.public,
    password: str = None,
    user: User = Depends(get_current_user),
    service: PastebinService = Depends()
):
    paste = await service.create_paste(
        content, user, title, language, privacy_level, password
    )
    return templates.TemplateResponse(
        "paste_success.html",
        {"request": request, "paste": paste}
    )
