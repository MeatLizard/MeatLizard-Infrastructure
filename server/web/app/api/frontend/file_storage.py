# server/web/app/api/frontend/file_storage.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="server/web/app/templates")

@router.get("/storage", response_class=HTMLResponse)
async def get_file_storage(request: Request):
    return templates.TemplateResponse("file_storage.html", {"request": request})
