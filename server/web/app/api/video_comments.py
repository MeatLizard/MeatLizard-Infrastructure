"""
Video comments API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import uuid

from ..db import get_db
from ..services.video_comments_service import VideoCommentsService
from ..dependencies import get_current_active_user
from ..models import User

router = APIRouter(prefix="/api/videos", tags=["video_comments"])

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000, description="Comment content")
    parent_comment_id: Optional[str] = Field(None, description="Parent comment ID for replies")

class CommentUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000, description="Updated comment content")

@router.post("/{video_id}/comments")
async def create_comment(
    video_id: str,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Create a new comment on a video."""
    try:
        video_uuid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID format"
        )
    
    parent_comment_uuid = None
    if comment_data.parent_comment_id:
        try:
            parent_comment_uuid = uuid.UUID(comment_data.parent_comment_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid parent comment ID format"
            )
    
    service = VideoCommentsService(db)
    result = await service.create_comment(
        video_id=video_uuid,
        user_id=current_user.id,
        content=comment_data.content,
        parent_comment_id=parent_comment_uuid
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found or parent comment not found"
        )
    
    return result

@router.get("/{video_id}/comments")
async def get_video_comments(
    video_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Comments per page"),
    sort: str = Query("newest", regex="^(newest|oldest|top)$", description="Sort order"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get comments for a video with pagination."""
    try:
        video_uuid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID format"
        )
    
    service = VideoCommentsService(db)
    result = await service.get_video_comments(
        video_id=video_uuid,
        page=page,
        limit=limit,
        sort_by=sort
    )
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    return result

@router.get("/{video_id}/comments/{comment_id}/replies")
async def get_comment_replies(
    video_id: str,
    comment_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=50, description="Replies per page"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get replies to a specific comment."""
    try:
        video_uuid = uuid.UUID(video_id)
        comment_uuid = uuid.UUID(comment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID or comment ID format"
        )
    
    service = VideoCommentsService(db)
    result = await service.get_comment_replies(
        video_id=video_uuid,
        comment_id=comment_uuid,
        page=page,
        limit=limit
    )
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video or comment not found"
        )
    
    return result

@router.put("/{video_id}/comments/{comment_id}")
async def update_comment(
    video_id: str,
    comment_id: str,
    comment_data: CommentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Update a comment (only by the comment author)."""
    try:
        video_uuid = uuid.UUID(video_id)
        comment_uuid = uuid.UUID(comment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID or comment ID format"
        )
    
    service = VideoCommentsService(db)
    result = await service.update_comment(
        video_id=video_uuid,
        comment_id=comment_uuid,
        user_id=current_user.id,
        content=comment_data.content
    )
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    
    if result.get("error") == "unauthorized":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own comments"
        )
    
    return result

@router.delete("/{video_id}/comments/{comment_id}")
async def delete_comment(
    video_id: str,
    comment_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Delete a comment (only by the comment author)."""
    try:
        video_uuid = uuid.UUID(video_id)
        comment_uuid = uuid.UUID(comment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID or comment ID format"
        )
    
    service = VideoCommentsService(db)
    result = await service.delete_comment(
        video_id=video_uuid,
        comment_id=comment_uuid,
        user_id=current_user.id
    )
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    
    if result.get("error") == "unauthorized":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments"
        )
    
    return result

@router.get("/{video_id}/comments/stats")
async def get_comment_stats(
    video_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get comment statistics for a video."""
    try:
        video_uuid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID format"
        )
    
    service = VideoCommentsService(db)
    result = await service.get_comment_stats(video_uuid)
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    return result