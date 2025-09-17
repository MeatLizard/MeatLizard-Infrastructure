"""
Viewing history service.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc, update, delete
from sqlalchemy.orm import selectinload
from typing import Dict, Any, Optional, List
import uuid
from datetime import datetime, timedelta
import json

from ..models import Video, ViewSession, User, VideoStatus, VideoVisibility
from .base_service import BaseService

class ViewingHistoryService(BaseService):
    """Service for managing user viewing history."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db)
    
    async def get_user_viewing_history(
        self, 
        user_id: uuid.UUID, 
        page: int = 1, 
        limit: int = 20,
        public_only: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get user's viewing history with pagination."""
        # Check if user exists and get privacy settings
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return None
        
        # Check privacy settings if requesting another user's history
        if public_only:
            # For now, assume history is private by default
            # In a real implementation, you'd have a user preferences table
            # For this demo, we'll allow public access
            pass
        
        # Calculate offset
        offset = (page - 1) * limit
        
        # Get viewing sessions with video information
        # Only get sessions where user actually watched something (> 5% completion)
        query = select(ViewSession).where(
            and_(
                ViewSession.user_id == user_id,
                ViewSession.completion_percentage >= 5,
                ViewSession.ended_at.isnot(None)
            )
        ).options(
            selectinload(ViewSession.video).selectinload(Video.creator)
        ).order_by(desc(ViewSession.last_heartbeat)).offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        sessions = result.scalars().all()
        
        # Get total count
        count_query = select(func.count(ViewSession.id)).where(
            and_(
                ViewSession.user_id == user_id,
                ViewSession.completion_percentage >= 5,
                ViewSession.ended_at.isnot(None)
            )
        )
        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar() or 0
        
        # Format history items
        history_items = []
        for session in sessions:
            if session.video and session.video.status == VideoStatus.ready:
                history_items.append({
                    "video_id": str(session.video.id),
                    "title": session.video.title,
                    "description": session.video.description,
                    "duration_seconds": session.video.duration_seconds,
                    "thumbnail_url": f"/api/videos/{session.video.id}/thumbnail" if session.video.thumbnail_s3_key else None,
                    "creator_name": session.video.creator.display_label,
                    "creator_id": str(session.video.creator_id),
                    "watched_at": session.last_heartbeat.isoformat(),
                    "watch_progress": {
                        "current_position_seconds": session.current_position_seconds,
                        "completion_percentage": session.completion_percentage,
                        "total_watch_time_seconds": session.total_watch_time_seconds
                    },
                    "can_resume": session.completion_percentage < 90,
                    "session_id": str(session.id)
                })
        
        return {
            "history": history_items,
            "user_id": str(user_id),
            "user_name": user.display_label,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit
            }
        }
    
    async def clear_viewing_history(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Clear all viewing history for a user."""
        # Count sessions to be cleared
        count_query = select(func.count(ViewSession.id)).where(
            ViewSession.user_id == user_id
        )
        count_result = await self.db.execute(count_query)
        count_to_clear = count_result.scalar() or 0
        
        # Delete all viewing sessions for the user
        delete_query = delete(ViewSession).where(ViewSession.user_id == user_id)
        await self.db.execute(delete_query)
        await self.db.commit()
        
        return {
            "cleared_count": count_to_clear
        }
    
    async def remove_video_from_history(
        self, 
        user_id: uuid.UUID, 
        video_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Remove a specific video from user's viewing history."""
        # Check if sessions exist
        existing_query = select(ViewSession).where(
            and_(
                ViewSession.user_id == user_id,
                ViewSession.video_id == video_id
            )
        )
        existing_result = await self.db.execute(existing_query)
        existing_sessions = existing_result.scalars().all()
        
        if not existing_sessions:
            return {"found": False}
        
        # Delete sessions for this video
        delete_query = delete(ViewSession).where(
            and_(
                ViewSession.user_id == user_id,
                ViewSession.video_id == video_id
            )
        )
        await self.db.execute(delete_query)
        await self.db.commit()
        
        return {
            "found": True,
            "removed_sessions": len(existing_sessions)
        }
    
    async def update_history_privacy(
        self, 
        user_id: uuid.UUID, 
        is_public: bool
    ) -> Dict[str, Any]:
        """Update user's viewing history privacy settings."""
        # In a real implementation, this would update a user preferences table
        # For now, we'll just return the setting
        # You would typically have a UserPreferences model
        
        return {
            "is_history_public": is_public,
            "updated_at": datetime.utcnow().isoformat()
        }
    
    async def get_history_privacy(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Get user's viewing history privacy settings."""
        # In a real implementation, this would query a user preferences table
        # For now, we'll return default private setting
        
        return {
            "user_id": str(user_id),
            "is_history_public": False  # Default to private
        }
    
    async def get_viewing_stats(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Get user's viewing statistics."""
        # Total videos watched
        total_videos_query = select(func.count(func.distinct(ViewSession.video_id))).where(
            and_(
                ViewSession.user_id == user_id,
                ViewSession.completion_percentage >= 5
            )
        )
        total_videos_result = await self.db.execute(total_videos_query)
        total_videos = total_videos_result.scalar() or 0
        
        # Total watch time
        total_time_query = select(func.sum(ViewSession.total_watch_time_seconds)).where(
            ViewSession.user_id == user_id
        )
        total_time_result = await self.db.execute(total_time_query)
        total_watch_time = total_time_result.scalar() or 0
        
        # Videos completed (>90%)
        completed_query = select(func.count(func.distinct(ViewSession.video_id))).where(
            and_(
                ViewSession.user_id == user_id,
                ViewSession.completion_percentage >= 90
            )
        )
        completed_result = await self.db.execute(completed_query)
        completed_videos = completed_result.scalar() or 0
        
        # Average completion rate
        avg_completion_query = select(func.avg(ViewSession.completion_percentage)).where(
            and_(
                ViewSession.user_id == user_id,
                ViewSession.completion_percentage > 0
            )
        )
        avg_completion_result = await self.db.execute(avg_completion_query)
        avg_completion = avg_completion_result.scalar() or 0
        
        # Most watched day of week (simplified)
        # In a real implementation, you'd extract day of week from timestamps
        
        return {
            "user_id": str(user_id),
            "total_videos_watched": total_videos,
            "total_watch_time_seconds": int(total_watch_time),
            "total_watch_time_formatted": self._format_duration(int(total_watch_time)),
            "completed_videos": completed_videos,
            "average_completion_percentage": round(float(avg_completion), 1),
            "completion_rate": round((completed_videos / total_videos * 100), 1) if total_videos > 0 else 0
        }
    
    async def get_recommendations(
        self, 
        user_id: uuid.UUID, 
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get video recommendations based on viewing history."""
        # Simple recommendation algorithm based on:
        # 1. Videos from creators the user has watched
        # 2. Videos similar to ones they completed
        # 3. Popular videos they haven't seen
        
        # Get creators the user has watched
        watched_creators_query = select(func.distinct(Video.creator_id)).select_from(
            ViewSession.__table__.join(Video.__table__)
        ).where(
            and_(
                ViewSession.user_id == user_id,
                ViewSession.completion_percentage >= 50
            )
        )
        watched_creators_result = await self.db.execute(watched_creators_query)
        watched_creator_ids = [row[0] for row in watched_creators_result.fetchall()]
        
        # Get videos the user has already watched
        watched_videos_query = select(func.distinct(ViewSession.video_id)).where(
            ViewSession.user_id == user_id
        )
        watched_videos_result = await self.db.execute(watched_videos_query)
        watched_video_ids = [row[0] for row in watched_videos_result.fetchall()]
        
        recommendations = []
        
        if watched_creator_ids:
            # Get videos from creators the user likes
            creator_videos_query = select(Video).where(
                and_(
                    Video.creator_id.in_(watched_creator_ids),
                    Video.id.notin_(watched_video_ids) if watched_video_ids else True,
                    Video.status == VideoStatus.ready,
                    Video.visibility == VideoVisibility.public
                )
            ).options(selectinload(Video.creator)).order_by(desc(Video.created_at)).limit(limit)
            
            creator_videos_result = await self.db.execute(creator_videos_query)
            creator_videos = creator_videos_result.scalars().all()
            
            for video in creator_videos:
                recommendations.append({
                    "video_id": str(video.id),
                    "title": video.title,
                    "description": video.description,
                    "duration_seconds": video.duration_seconds,
                    "thumbnail_url": f"/api/videos/{video.id}/thumbnail" if video.thumbnail_s3_key else None,
                    "creator_name": video.creator.display_label,
                    "creator_id": str(video.creator_id),
                    "created_at": video.created_at.isoformat(),
                    "recommendation_reason": "From creators you watch"
                })
        
        # If we need more recommendations, add popular videos
        if len(recommendations) < limit:
            remaining_limit = limit - len(recommendations)
            
            # Get popular videos (most viewed in last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            popular_videos_query = select(
                Video,
                func.count(ViewSession.id).label('view_count')
            ).select_from(
                Video.__table__.outerjoin(ViewSession.__table__)
            ).where(
                and_(
                    Video.id.notin_(watched_video_ids) if watched_video_ids else True,
                    Video.status == VideoStatus.ready,
                    Video.visibility == VideoVisibility.public,
                    or_(
                        ViewSession.started_at >= thirty_days_ago,
                        ViewSession.started_at.is_(None)
                    )
                )
            ).options(selectinload(Video.creator)).group_by(Video.id).order_by(
                desc('view_count'), desc(Video.created_at)
            ).limit(remaining_limit)
            
            popular_videos_result = await self.db.execute(popular_videos_query)
            popular_videos = popular_videos_result.all()
            
            for video, view_count in popular_videos:
                recommendations.append({
                    "video_id": str(video.id),
                    "title": video.title,
                    "description": video.description,
                    "duration_seconds": video.duration_seconds,
                    "thumbnail_url": f"/api/videos/{video.id}/thumbnail" if video.thumbnail_s3_key else None,
                    "creator_name": video.creator.display_label,
                    "creator_id": str(video.creator_id),
                    "created_at": video.created_at.isoformat(),
                    "view_count": view_count,
                    "recommendation_reason": "Popular videos"
                })
        
        return {
            "recommendations": recommendations[:limit],
            "user_id": str(user_id),
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def get_continue_watching(
        self, 
        user_id: uuid.UUID, 
        limit: int = 5
    ) -> Dict[str, Any]:
        """Get videos the user can continue watching."""
        # Get videos with 10-90% completion that were watched recently
        query = select(ViewSession).where(
            and_(
                ViewSession.user_id == user_id,
                ViewSession.completion_percentage >= 10,
                ViewSession.completion_percentage <= 90,
                ViewSession.last_heartbeat >= datetime.utcnow() - timedelta(days=30)
            )
        ).options(
            selectinload(ViewSession.video).selectinload(Video.creator)
        ).order_by(desc(ViewSession.last_heartbeat)).limit(limit)
        
        result = await self.db.execute(query)
        sessions = result.scalars().all()
        
        continue_watching = []
        for session in sessions:
            if session.video and session.video.status == VideoStatus.ready:
                continue_watching.append({
                    "video_id": str(session.video.id),
                    "title": session.video.title,
                    "description": session.video.description,
                    "duration_seconds": session.video.duration_seconds,
                    "thumbnail_url": f"/api/videos/{session.video.id}/thumbnail" if session.video.thumbnail_s3_key else None,
                    "creator_name": session.video.creator.display_label,
                    "creator_id": str(session.video.creator_id),
                    "last_watched": session.last_heartbeat.isoformat(),
                    "resume_position_seconds": session.current_position_seconds,
                    "completion_percentage": session.completion_percentage,
                    "remaining_seconds": session.video.duration_seconds - session.current_position_seconds,
                    "session_id": str(session.id)
                })
        
        return {
            "continue_watching": continue_watching,
            "user_id": str(user_id)
        }
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in seconds to human readable format."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{hours}h"