# server/web/app/api/frontend/video_player.py
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from server.web.app.db import get_db_session
from server.web.app.models import Video, VideoStatus, VideoVisibility

router = APIRouter()
templates = Jinja2Templates(directory="server/web/app/templates")

@router.get("/player", response_class=HTMLResponse)
async def get_video_player(
    request: Request,
    v: Optional[str] = None,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Serve the adaptive video player page.
    
    Args:
        v: Video ID parameter
        user_id: User ID for access control (optional)
    
    Returns:
        HTML response with video player
    """
    video_data = None
    
    if v:
        try:
            # Get video information
            video = await db.get(Video, v)
            if video:
                # Basic access check (detailed check will be done by JavaScript)
                if video.visibility == VideoVisibility.public or video.visibility == VideoVisibility.unlisted:
                    video_data = {
                        "id": str(video.id),
                        "title": video.title,
                        "description": video.description,
                        "duration": video.duration_seconds,
                        "status": video.status.value,
                        "visibility": video.visibility.value,
                        "thumbnail_url": f"/api/videos/{video.id}/thumbnail" if video.thumbnail_s3_key else None
                    }
                elif video.visibility == VideoVisibility.private and user_id == str(video.creator_id):
                    video_data = {
                        "id": str(video.id),
                        "title": video.title,
                        "description": video.description,
                        "duration": video.duration_seconds,
                        "status": video.status.value,
                        "visibility": video.visibility.value,
                        "thumbnail_url": f"/api/videos/{video.id}/thumbnail" if video.thumbnail_s3_key else None
                    }
        except Exception as e:
            # Log error but continue to serve player (JavaScript will handle the error)
            pass
    
    return templates.TemplateResponse("video_player.html", {
        "request": request,
        "video_id": v,
        "video_data": video_data,
        "user_id": user_id
    })

@router.get("/watch", response_class=HTMLResponse)
async def watch_video(
    request: Request,
    v: str,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Watch video page (alias for player with required video ID).
    
    Args:
        v: Video ID (required)
        user_id: User ID for access control (optional)
    
    Returns:
        HTML response with video player
    """
    return await get_video_player(request, v, user_id, db)
