# server/web/app/api/frontend/pastebin.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="server/web/app/templates")

@router.get("/pastebin", response_class=HTMLResponse)
async def get_pastebin(request: Request):
    return templates.TemplateResponse("pastebin.html", {"request": request})