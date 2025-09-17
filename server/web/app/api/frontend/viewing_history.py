# server/web/app/api/frontend/viewing_history.py
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from server.web.app.db import get_db_session
from server.web.app.models import ViewSession, Video

router = APIRouter()
templates = Jinja2Templates(directory="server/web/app/templates")

@router.get("/history", response_class=HTMLResponse)
async def get_viewing_history_page(
    request: Request,
    user_id: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Serve the viewing history page.
    
    Args:
        user_id: User identifier (required for viewing history)
        limit: Maximum number of records to return
        offset: Number of records to skip
    
    Returns:
        HTML response with viewing history
    """
    if not user_id:
        return templates.TemplateResponse("viewing_history.html", {
            "request": request,
            "error": "User authentication required to view history",
            "history": []
        })
    
    try:
        # Get viewing sessions for user
        result = await db.execute(
            select(ViewSession, Video)
            .join(Video, ViewSession.video_id == Video.id)
            .where(ViewSession.user_id == user_id)
            .order_by(ViewSession.last_heartbeat.desc())
            .limit(limit)
            .offset(offset)
        )
        
        sessions_and_videos = result.all()
        
        history = []
        for session, video in sessions_and_videos:
            history.append({
                "session_id": str(session.id),
                "video_id": str(video.id),
                "video_title": video.title,
                "video_description": video.description,
                "video_duration": video.duration_seconds,
                "current_position": session.current_position_seconds,
                "completion_percentage": session.completion_percentage,
                "total_watch_time": session.total_watch_time_seconds,
                "last_watched": session.last_heartbeat,
                "can_resume": session.current_position_seconds > 30 and session.completion_percentage < 95,
                "thumbnail_url": f"/api/videos/{video.id}/thumbnail" if video.thumbnail_s3_key else None,
                "watch_url": f"/watch?v={video.id}"
            })
        
        return templates.TemplateResponse("viewing_history.html", {
            "request": request,
            "user_id": user_id,
            "history": history,
            "limit": limit,
            "offset": offset,
            "has_more": len(history) == limit
        })
        
    except Exception as e:
        return templates.TemplateResponse("viewing_history.html", {
            "request": request,
            "error": f"Failed to load viewing history: {str(e)}",
            "history": []
        })