
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from server.web.app.services.leaderboard_service import LeaderboardService

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/leaderboard/{leaderboard_name}", response_class=HTMLResponse)
async def get_leaderboard(
    request: Request,
    leaderboard_name: str,
    service: LeaderboardService = Depends()
):
    leaderboard_data = await service.get_leaderboard(leaderboard_name)
    return templates.TemplateResponse(
        "leaderboard.html",
        {"request": request, "leaderboard_data": leaderboard_data}
    )
