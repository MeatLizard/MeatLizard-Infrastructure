"""
Frontend routes for Media Import interface.
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ...dependencies import get_current_user
from ...models import User

router = APIRouter()
templates = Jinja2Templates(directory="server/web/app/templates")

@router.get("/media-import", response_class=HTMLResponse)
async def media_import_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Media import interface page"""
    return templates.TemplateResponse(
        "media_import.html",
        {
            "request": request,
            "user": current_user,
            "page_title": "Media Import"
        }
    )