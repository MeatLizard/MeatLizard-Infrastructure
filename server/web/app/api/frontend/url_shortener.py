
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from server.web.app.services.url_shortener_service import URLShortenerService, get_url_shortener_service
from server.web.app.middleware.permissions import get_current_user
from server.web.app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/shorten", response_class=HTMLResponse)
async def get_shorten_form(request: Request):
    return templates.TemplateResponse("shorten.html", {"request": request})

@router.post("/shorten", response_class=HTMLResponse)
async def create_short_url(
    request: Request,
    target_url: str,
    custom_slug: str = None,
    user: User = Depends(get_current_user),
    service: URLShortenerService = Depends(get_url_shortener_service)
):
    short_url = await service.create_short_url(target_url, user, custom_slug)
    return templates.TemplateResponse(
        "shorten_success.html",
        {"request": request, "short_url": short_url}
    )
