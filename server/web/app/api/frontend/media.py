
from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from server.web.app.services.media_upload_service import MediaUploadService
from server.web.app.middleware.permissions import get_current_user
from server.web.app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/upload", response_class=HTMLResponse)
async def get_upload_form(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@router.post("/upload", response_class=HTMLResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    service: MediaUploadService = Depends()
):
    media_file = await service.upload_file(file, user)
    return templates.TemplateResponse(
        "upload_success.html",
        {"request": request, "media_file": media_file}
    )
