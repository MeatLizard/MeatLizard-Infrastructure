"""
Frontend routes for channel management.
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ...dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="server/web/app/templates")


@router.get("/channels", response_class=HTMLResponse)
async def channels_page(
    request: Request,
    current_user = Depends(get_current_user)
):
    """Channel management page."""
    return templates.TemplateResponse(
        "channels.html",
        {"request": request, "user": current_user}
    )


@router.get("/channels/{channel_id}", response_class=HTMLResponse)
async def channel_detail_page(
    request: Request,
    channel_id: str,
    current_user = Depends(get_current_user, use_cache=False)
):
    """Individual channel page."""
    return templates.TemplateResponse(
        "channel_detail.html",
        {"request": request, "user": current_user, "channel_id": channel_id}
    )


@router.get("/playlists", response_class=HTMLResponse)
async def playlists_page(
    request: Request,
    current_user = Depends(get_current_user)
):
    """Playlist management page."""
    return templates.TemplateResponse(
        "playlists.html",
        {"request": request, "user": current_user}
    )


@router.get("/playlists/{playlist_id}", response_class=HTMLResponse)
async def playlist_detail_page(
    request: Request,
    playlist_id: str,
    current_user = Depends(get_current_user, use_cache=False)
):
    """Individual playlist page."""
    return templates.TemplateResponse(
        "playlist_detail.html",
        {"request": request, "user": current_user, "playlist_id": playlist_id}
    )


@router.get("/browse", response_class=HTMLResponse)
async def browse_page(
    request: Request,
    current_user = Depends(get_current_user, use_cache=False)
):
    """Content browsing and discovery page."""
    return templates.TemplateResponse(
        "browse.html",
        {"request": request, "user": current_user}
    )


@router.get("/", response_class=HTMLResponse)
async def home_page(
    request: Request,
    current_user = Depends(get_current_user, use_cache=False)
):
    """Home page with content discovery."""
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "user": current_user}
    )