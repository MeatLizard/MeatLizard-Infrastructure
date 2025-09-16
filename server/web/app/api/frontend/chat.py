
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from server.web.app.services.chat_service import ChatService
from server.web.app.middleware.permissions import get_current_user
from server.web.app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/chat", response_class=HTMLResponse)
async def get_chat_window(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@router.post("/chat", response_class=HTMLResponse)
async def chat(
    request: Request,
    message: str,
    user: User = Depends(get_current_user),
    service: ChatService = Depends()
):
    response = await service.send_message(user, message)
    return templates.TemplateResponse(
        "chat_response.html",
        {"request": request, "response": response}
    )
