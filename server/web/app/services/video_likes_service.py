"""
Video likes/dislikes service.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Dict, Any, Optional
import uuid
from datetime import datetime

from ..models import Video, VideoLike, User
from .base_service import BaseService

class VideoLikesService(BaseService):
    """Service for managing video likes and dislikes."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db)
    
    async def like_video(self, video_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Like a video. If user already disliked, change to like.
        If user already liked, remove the like.
        """
        # Check if video exists
        video_result = await self.db.execute(
            select(Video).where(Video.id == video_id)
        )
        video = video_result.scalar_one_or_none()
        
        if not video:
            return None
        
        # Check existing like/dislike
        existing_result = await self.db.execute(
            select(VideoLike).where(
                and_(VideoLike.video_id == video_id, VideoLike.user_id == user_id)
            )
        )
        existing_like = existing_result.scalar_one_or_none()
        
        if existing_like:
            if existing_like.is_like:
                # User already liked, remove the like
                await self.db.delete(existing_like)
                action = "removed_like"
            else:
                # User disliked, change to like
                existing_like.is_like = True
                existing_like.created_at = datetime.utcnow()
                action = "changed_to_like"
        else:
            # No existing like/dislike, create new like
            new_like = VideoLike(
                video_id=video_id,
                user_id=user_id,
                is_like=True
            )
            self.db.add(new_like)
            action = "liked"
        
        await self.db.commit()
        
        # Get updated counts
        counts = await self._get_like_counts(video_id)
        
        return {
            "action": action,
            "like_count": counts["like_count"],
            "dislike_count": counts["dislike_count"],
            "user_status": "liked" if action != "removed_like" else None
        }
    
    async def dislike_video(self, video_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Dislike a video. If user already liked, change to dislike.
        If user already disliked, remove the dislike.
        """
        # Check if video exists
        video_result = await self.db.execute(
            select(Video).where(Video.id == video_id)
        )
        video = video_result.scalar_one_or_none()
        
        if not video:
            return None
        
        # Check existing like/dislike
        existing_result = await self.db.execute(
            select(VideoLike).where(
                and_(VideoLike.video_id == video_id, VideoLike.user_id == user_id)
            )
        )
        existing_like = existing_result.scalar_one_or_none()
        
        if existing_like:
            if not existing_like.is_like:
                # User already disliked, remove the dislike
                await self.db.delete(existing_like)
                action = "removed_dislike"
            else:
                # User liked, change to dislike
                existing_like.is_like = False
                existing_like.created_at = datetime.utcnow()
                action = "changed_to_dislike"
        else:
            # No existing like/dislike, create new dislike
            new_dislike = VideoLike(
                video_id=video_id,
                user_id=user_id,
                is_like=False
            )
            self.db.add(new_dislike)
            action = "disliked"
        
        await self.db.commit()
        
        # Get updated counts
        counts = await self._get_like_counts(video_id)
        
        return {
            "action": action,
            "like_count": counts["like_count"],
            "dislike_count": counts["dislike_count"],
            "user_status": "disliked" if action != "removed_dislike" else None
        }
    
    async def remove_like_dislike(self, video_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Remove any existing like or dislike from a video."""
        # Check if video exists
        video_result = await self.db.execute(
            select(Video).where(Video.id == video_id)
        )
        video = video_result.scalar_one_or_none()
        
        if not video:
            return None
        
        # Check existing like/dislike
        existing_result = await self.db.execute(
            select(VideoLike).where(
                and_(VideoLike.video_id == video_id, VideoLike.user_id == user_id)
            )
        )
        existing_like = existing_result.scalar_one_or_none()
        
        if existing_like:
            await self.db.delete(existing_like)
            await self.db.commit()
            action = "removed"
        else:
            action = "no_change"
        
        # Get updated counts
        counts = await self._get_like_counts(video_id)
        
        return {
            "action": action,
            "like_count": counts["like_count"],
            "dislike_count": counts["dislike_count"],
            "user_status": None
        }
    
    async def get_video_likes(self, video_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get like and dislike counts for a video."""
        # Check if video exists
        video_result = await self.db.execute(
            select(Video).where(Video.id == video_id)
        )
        video = video_result.scalar_one_or_none()
        
        if not video:
            return None
        
        counts = await self._get_like_counts(video_id)
        
        return {
            "video_id": str(video_id),
            "like_count": counts["like_count"],
            "dislike_count": counts["dislike_count"]
        }
    
    async def get_user_like_status(self, video_id: uuid.UUID, user_id: uuid.UUID) -> Dict[str, Any]:
        """Get current user's like/dislike status for a video."""
        existing_result = await self.db.execute(
            select(VideoLike).where(
                and_(VideoLike.video_id == video_id, VideoLike.user_id == user_id)
            )
        )
        existing_like = existing_result.scalar_one_or_none()
        
        if existing_like:
            status = "liked" if existing_like.is_like else "disliked"
        else:
            status = None
        
        return {
            "video_id": str(video_id),
            "user_status": status
        }
    
    async def _get_like_counts(self, video_id: uuid.UUID) -> Dict[str, int]:
        """Get like and dislike counts for a video."""
        # Get like count
        like_result = await self.db.execute(
            select(func.count(VideoLike.id)).where(
                and_(VideoLike.video_id == video_id, VideoLike.is_like == True)
            )
        )
        like_count = like_result.scalar() or 0
        
        # Get dislike count
        dislike_result = await self.db.execute(
            select(func.count(VideoLike.id)).where(
                and_(VideoLike.video_id == video_id, VideoLike.is_like == False)
            )
        )
        dislike_count = dislike_result.scalar() or 0
        
        return {
            "like_count": like_count,
            "dislike_count": dislike_count
        }