"""
Frontend API for video settings page
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ...dependencies import get_current_user, get_db_session
from ...models import User, Video
from ...services.video_access_control_service import VideoAccessControlService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter(tags=["frontend-video-settings"])
templates = Jinja2Templates(directory="server/web/app/templates")


@router.get("/videos/{video_id}/settings", response_class=HTMLResponse)
async def video_settings_page(
    video_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Render the video settings page
    """
    # Get video and verify ownership
    stmt = select(Video).where(Video.id == video_id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Check if user can manage this video
    if video.creator_id != current_user.id:
        # TODO: Add admin role check here
        raise HTTPException(status_code=403, detail="You don't have permission to manage this video")
    
    return templates.TemplateResponse("video_settings.html", {
        "request": request,
        "video": video,
        "current_user": current_user
    })


@router.get("/api/users/search")
async def search_users(
    q: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Search for users by name or email
    """
    if len(q) < 2:
        return []
    
    # Search users by display name or email
    stmt = select(User).where(
        (User.display_label.ilike(f"%{q}%")) |
        (User.email.ilike(f"%{q}%"))
    ).limit(10)
    
    result = await db.execute(stmt)
    users = result.scalars().all()
    
    return [
        {
            "id": str(user.id),
            "display_label": user.display_label,
            "email": user.email
        }
        for user in users
        if user.id != current_user.id  # Exclude current user
    ]


@router.get("/api/videos/{video_id}/analytics")
async def get_video_analytics(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get analytics data for a video
    """
    # Verify video ownership
    stmt = select(Video).where(Video.id == video_id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    if video.creator_id != current_user.id:
        # TODO: Add admin role check here
        raise HTTPException(status_code=403, detail="You don't have permission to view analytics for this video")
    
    # Get analytics from database
    from ...models import AnalyticsEvent, ViewSession
    from sqlalchemy import func, distinct
    
    # Total views (completed view sessions)
    total_views_stmt = select(func.count(ViewSession.id)).where(
        ViewSession.video_id == video_id,
        ViewSession.ended_at.isnot(None)
    )
    total_views_result = await db.execute(total_views_stmt)
    total_views = total_views_result.scalar() or 0
    
    # Unique viewers
    unique_viewers_stmt = select(func.count(distinct(ViewSession.user_id))).where(
        ViewSession.video_id == video_id,
        ViewSession.user_id.isnot(None)
    )
    unique_viewers_result = await db.execute(unique_viewers_stmt)
    unique_viewers = unique_viewers_result.scalar() or 0
    
    # Access attempts
    access_attempts_stmt = select(func.count(AnalyticsEvent.id)).where(
        AnalyticsEvent.event_type == "video_access_attempt",
        AnalyticsEvent.content_id == video_id
    )
    access_attempts_result = await db.execute(access_attempts_stmt)
    access_attempts = access_attempts_result.scalar() or 0
    
    # Denied access
    denied_access_stmt = select(func.count(AnalyticsEvent.id)).where(
        AnalyticsEvent.event_type == "video_access_attempt",
        AnalyticsEvent.content_id == video_id,
        AnalyticsEvent.data['access_granted'].astext == 'false'
    )
    denied_access_result = await db.execute(denied_access_stmt)
    denied_access = denied_access_result.scalar() or 0
    
    return {
        "total_views": total_views,
        "unique_viewers": unique_viewers,
        "access_attempts": access_attempts,
        "denied_access": denied_access
    }