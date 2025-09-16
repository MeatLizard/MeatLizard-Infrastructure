# server/web/app/api/frontend/url_shortener.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="server/web/app/templates")

@router.get("/url-shortener", response_class=HTMLResponse)
async def get_url_shortener(request: Request):
    return templates.TemplateResponse("url_shortener.html", {"request": request})