"""
Video likes/dislikes API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import uuid

from ..db import get_db
from ..services.video_likes_service import VideoLikesService
from ..dependencies import get_current_active_user
from ..models import User

router = APIRouter(prefix="/api/videos", tags=["video_likes"])

@router.post("/{video_id}/like")
async def like_video(
    video_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Like a video."""
    try:
        video_uuid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID format"
        )
    
    service = VideoLikesService(db)
    result = await service.like_video(video_uuid, current_user.id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    return result

@router.post("/{video_id}/dislike")
async def dislike_video(
    video_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Dislike a video."""
    try:
        video_uuid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID format"
        )
    
    service = VideoLikesService(db)
    result = await service.dislike_video(video_uuid, current_user.id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    return result

@router.delete("/{video_id}/like")
async def remove_like_dislike(
    video_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Remove like/dislike from a video."""
    try:
        video_uuid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID format"
        )
    
    service = VideoLikesService(db)
    result = await service.remove_like_dislike(video_uuid, current_user.id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    return result

@router.get("/{video_id}/likes")
async def get_video_likes(
    video_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get like/dislike counts for a video."""
    try:
        video_uuid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID format"
        )
    
    service = VideoLikesService(db)
    result = await service.get_video_likes(video_uuid)
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    return result

@router.get("/{video_id}/user-like")
async def get_user_like_status(
    video_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get current user's like/dislike status for a video."""
    try:
        video_uuid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID format"
        )
    
    service = VideoLikesService(db)
    result = await service.get_user_like_status(video_uuid, current_user.id)
    
    return result