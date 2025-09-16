# server/web/app/api/frontend/video_player.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="server/web/app/templates")

@router.get("/player", response_class=HTMLResponse)
async def get_video_player(request: Request):
    return templates.TemplateResponse("video_player.html", {"request": request})
