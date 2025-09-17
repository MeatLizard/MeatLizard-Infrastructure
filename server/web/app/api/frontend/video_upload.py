"""
Video Upload Frontend Routes

Provides HTML page routes for video upload functionality.
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from server.web.app.models import User
from server.web.app.middleware.permissions import get_current_user

router = APIRouter(tags=["video-upload-frontend"])
templates = Jinja2Templates(directory="server/web/app/templates")


@router.get("/upload", response_class=HTMLResponse)
async def video_upload_page(
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    Video upload page with metadata collection interface.
    
    This page provides a comprehensive interface for uploading videos
    with title, description, tags, and quality preset selection.
    
    Requirements: 3.1, 3.5
    """
    return templates.TemplateResponse("video_upload.html", {
        "request": request,
        "user": user,
        "page_title": "Upload Video"
    })


@router.get("/upload/help", response_class=HTMLResponse)
async def video_upload_help(
    request: Request,
    user: User = Depends(get_current_user)
):
    """
    Help page for video upload with guidelines and requirements.
    
    This page provides information about supported formats, size limits,
    and best practices for video uploads.
    
    Requirements: 3.1
    """
    return templates.TemplateResponse("video_upload_help.html", {
        "request": request,
        "user": user,
        "page_title": "Upload Help",
        "supported_formats": ["MP4", "MOV", "AVI", "MKV", "WebM"],
        "max_file_size": "10 GB",
        "max_duration": "4 hours",
        "recommended_settings": {
            "resolution": "1080p or higher",
            "framerate": "30 or 60 FPS",
            "bitrate": "5-10 Mbps for 1080p",
            "codec": "H.264 or H.265"
        }
    })