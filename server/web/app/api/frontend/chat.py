# server/web/app/api/frontend/chat.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="server/web/app/templates")


@router.get("/chat", response_class=HTMLResponse)
async def get_chat_window(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})