"""
User viewing history API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import uuid

from ..db import get_db
from ..services.viewing_history_service import ViewingHistoryService
from ..dependencies import get_current_active_user
from ..models import User

router = APIRouter(prefix="/api/users", tags=["viewing_history"])

class HistoryPrivacyUpdate(BaseModel):
    is_history_public: bool = Field(..., description="Whether viewing history should be public")

@router.get("/me/viewing-history")
async def get_user_viewing_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get current user's viewing history."""
    service = ViewingHistoryService(db)
    
    result = await service.get_user_viewing_history(
        user_id=current_user.id,
        page=page,
        limit=limit
    )
    
    return result

@router.get("/{user_id}/viewing-history")
async def get_public_viewing_history(
    user_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: Optional[User] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get a user's public viewing history."""
    try:
        target_user_id = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    service = ViewingHistoryService(db)
    
    # Check if requesting own history or public history
    is_own_history = current_user and current_user.id == target_user_id
    
    result = await service.get_user_viewing_history(
        user_id=target_user_id,
        page=page,
        limit=limit,
        public_only=not is_own_history
    )
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or viewing history is private"
        )
    
    return result

@router.delete("/me/viewing-history")
async def clear_viewing_history(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Clear current user's viewing history."""
    service = ViewingHistoryService(db)
    
    result = await service.clear_viewing_history(current_user.id)
    
    return {
        "message": "Viewing history cleared successfully",
        "cleared_count": result["cleared_count"]
    }

@router.delete("/me/viewing-history/{video_id}")
async def remove_video_from_history(
    video_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Remove a specific video from viewing history."""
    try:
        video_uuid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video ID format"
        )
    
    service = ViewingHistoryService(db)
    
    result = await service.remove_video_from_history(current_user.id, video_uuid)
    
    if not result["found"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found in viewing history"
        )
    
    return {
        "message": "Video removed from viewing history",
        "video_id": video_id
    }

@router.put("/me/history-privacy")
async def update_history_privacy(
    privacy_data: HistoryPrivacyUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Update viewing history privacy settings."""
    service = ViewingHistoryService(db)
    
    result = await service.update_history_privacy(
        user_id=current_user.id,
        is_public=privacy_data.is_history_public
    )
    
    return {
        "message": "History privacy settings updated",
        "is_history_public": result["is_history_public"]
    }

@router.get("/me/history-privacy")
async def get_history_privacy(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get current user's history privacy settings."""
    service = ViewingHistoryService(db)
    
    result = await service.get_history_privacy(current_user.id)
    
    return result

@router.get("/me/viewing-stats")
async def get_viewing_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get current user's viewing statistics."""
    service = ViewingHistoryService(db)
    
    result = await service.get_viewing_stats(current_user.id)
    
    return result

@router.get("/me/recommendations")
async def get_recommendations(
    limit: int = Query(10, ge=1, le=50, description="Number of recommendations"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get video recommendations based on viewing history."""
    service = ViewingHistoryService(db)
    
    result = await service.get_recommendations(
        user_id=current_user.id,
        limit=limit
    )
    
    return result

@router.get("/me/continue-watching")
async def get_continue_watching(
    limit: int = Query(5, ge=1, le=20, description="Number of videos to return"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get videos the user can continue watching."""
    service = ViewingHistoryService(db)
    
    result = await service.get_continue_watching(
        user_id=current_user.id,
        limit=limit
    )
    
    return result