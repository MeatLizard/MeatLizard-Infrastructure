"""
Video comments service.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload
from typing import Dict, Any, Optional, List
import uuid
from datetime import datetime
import re

from ..models import Video, VideoComment, User
from .base_service import BaseService

class VideoCommentsService(BaseService):
    """Service for managing video comments."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db)
    
    async def create_comment(
        self, 
        video_id: uuid.UUID, 
        user_id: uuid.UUID, 
        content: str,
        parent_comment_id: Optional[uuid.UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new comment on a video."""
        # Check if video exists
        video_result = await self.db.execute(
            select(Video).where(Video.id == video_id)
        )
        video = video_result.scalar_one_or_none()
        
        if not video:
            return None
        
        # If parent comment specified, check if it exists and belongs to this video
        if parent_comment_id:
            parent_result = await self.db.execute(
                select(VideoComment).where(
                    and_(
                        VideoComment.id == parent_comment_id,
                        VideoComment.video_id == video_id,
                        VideoComment.is_deleted == False
                    )
                )
            )
            parent_comment = parent_result.scalar_one_or_none()
            
            if not parent_comment:
                return None
        
        # Validate and clean content
        cleaned_content = self._clean_content(content)
        if not cleaned_content:
            return {"error": "invalid_content", "message": "Comment content is invalid"}
        
        # Check for spam/moderation
        moderation_result = await self._moderate_content(cleaned_content, user_id)
        if not moderation_result["allowed"]:
            return {
                "error": "moderation_failed", 
                "message": moderation_result["reason"]
            }
        
        # Create comment
        comment = VideoComment(
            video_id=video_id,
            user_id=user_id,
            parent_comment_id=parent_comment_id,
            content=cleaned_content
        )
        
        self.db.add(comment)
        await self.db.commit()
        await self.db.refresh(comment)
        
        # Load user information
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one()
        
        return {
            "id": str(comment.id),
            "video_id": str(video_id),
            "user_id": str(user_id),
            "user_name": user.display_label,
            "content": comment.content,
            "parent_comment_id": str(parent_comment_id) if parent_comment_id else None,
            "is_deleted": False,
            "created_at": comment.created_at.isoformat(),
            "updated_at": comment.updated_at.isoformat(),
            "reply_count": 0
        }
    
    async def get_video_comments(
        self, 
        video_id: uuid.UUID, 
        page: int = 1, 
        limit: int = 20,
        sort_by: str = "newest"
    ) -> Optional[Dict[str, Any]]:
        """Get comments for a video with pagination."""
        # Check if video exists
        video_result = await self.db.execute(
            select(Video).where(Video.id == video_id)
        )
        video = video_result.scalar_one_or_none()
        
        if not video:
            return None
        
        # Calculate offset
        offset = (page - 1) * limit
        
        # Build query for top-level comments (no parent)
        query = select(VideoComment).where(
            and_(
                VideoComment.video_id == video_id,
                VideoComment.parent_comment_id.is_(None),
                VideoComment.is_deleted == False
            )
        ).options(selectinload(VideoComment.user))
        
        # Apply sorting
        if sort_by == "newest":
            query = query.order_by(desc(VideoComment.created_at))
        elif sort_by == "oldest":
            query = query.order_by(asc(VideoComment.created_at))
        elif sort_by == "top":
            # For now, sort by creation time. In future, could sort by likes/engagement
            query = query.order_by(desc(VideoComment.created_at))
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        # Execute query
        result = await self.db.execute(query)
        comments = result.scalars().all()
        
        # Get total count for pagination
        count_query = select(func.count(VideoComment.id)).where(
            and_(
                VideoComment.video_id == video_id,
                VideoComment.parent_comment_id.is_(None),
                VideoComment.is_deleted == False
            )
        )
        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar() or 0
        
        # Format comments with reply counts
        formatted_comments = []
        for comment in comments:
            reply_count = await self._get_reply_count(comment.id)
            formatted_comments.append({
                "id": str(comment.id),
                "video_id": str(comment.video_id),
                "user_id": str(comment.user_id),
                "user_name": comment.user.display_label,
                "content": comment.content,
                "parent_comment_id": None,
                "is_deleted": comment.is_deleted,
                "created_at": comment.created_at.isoformat(),
                "updated_at": comment.updated_at.isoformat(),
                "reply_count": reply_count
            })
        
        return {
            "comments": formatted_comments,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit
            }
        }
    
    async def get_comment_replies(
        self, 
        video_id: uuid.UUID, 
        comment_id: uuid.UUID,
        page: int = 1, 
        limit: int = 10
    ) -> Optional[Dict[str, Any]]:
        """Get replies to a specific comment."""
        # Check if parent comment exists and belongs to video
        parent_result = await self.db.execute(
            select(VideoComment).where(
                and_(
                    VideoComment.id == comment_id,
                    VideoComment.video_id == video_id,
                    VideoComment.is_deleted == False
                )
            )
        )
        parent_comment = parent_result.scalar_one_or_none()
        
        if not parent_comment:
            return None
        
        # Calculate offset
        offset = (page - 1) * limit
        
        # Get replies
        query = select(VideoComment).where(
            and_(
                VideoComment.parent_comment_id == comment_id,
                VideoComment.is_deleted == False
            )
        ).options(selectinload(VideoComment.user)).order_by(asc(VideoComment.created_at)).offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        replies = result.scalars().all()
        
        # Get total count
        count_query = select(func.count(VideoComment.id)).where(
            and_(
                VideoComment.parent_comment_id == comment_id,
                VideoComment.is_deleted == False
            )
        )
        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar() or 0
        
        # Format replies
        formatted_replies = []
        for reply in replies:
            formatted_replies.append({
                "id": str(reply.id),
                "video_id": str(reply.video_id),
                "user_id": str(reply.user_id),
                "user_name": reply.user.display_label,
                "content": reply.content,
                "parent_comment_id": str(reply.parent_comment_id),
                "is_deleted": reply.is_deleted,
                "created_at": reply.created_at.isoformat(),
                "updated_at": reply.updated_at.isoformat(),
                "reply_count": 0  # Replies don't have sub-replies
            })
        
        return {
            "replies": formatted_replies,
            "parent_comment_id": str(comment_id),
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit
            }
        }
    
    async def update_comment(
        self, 
        video_id: uuid.UUID, 
        comment_id: uuid.UUID, 
        user_id: uuid.UUID,
        content: str
    ) -> Optional[Dict[str, Any]]:
        """Update a comment (only by the author)."""
        # Get comment
        comment_result = await self.db.execute(
            select(VideoComment).where(
                and_(
                    VideoComment.id == comment_id,
                    VideoComment.video_id == video_id,
                    VideoComment.is_deleted == False
                )
            ).options(selectinload(VideoComment.user))
        )
        comment = comment_result.scalar_one_or_none()
        
        if not comment:
            return None
        
        # Check if user is the author
        if comment.user_id != user_id:
            return {"error": "unauthorized"}
        
        # Validate and clean content
        cleaned_content = self._clean_content(content)
        if not cleaned_content:
            return {"error": "invalid_content", "message": "Comment content is invalid"}
        
        # Check for spam/moderation
        moderation_result = await self._moderate_content(cleaned_content, user_id)
        if not moderation_result["allowed"]:
            return {
                "error": "moderation_failed", 
                "message": moderation_result["reason"]
            }
        
        # Update comment
        comment.content = cleaned_content
        comment.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(comment)
        
        reply_count = await self._get_reply_count(comment.id)
        
        return {
            "id": str(comment.id),
            "video_id": str(comment.video_id),
            "user_id": str(comment.user_id),
            "user_name": comment.user.display_label,
            "content": comment.content,
            "parent_comment_id": str(comment.parent_comment_id) if comment.parent_comment_id else None,
            "is_deleted": comment.is_deleted,
            "created_at": comment.created_at.isoformat(),
            "updated_at": comment.updated_at.isoformat(),
            "reply_count": reply_count
        }
    
    async def delete_comment(
        self, 
        video_id: uuid.UUID, 
        comment_id: uuid.UUID, 
        user_id: uuid.UUID
    ) -> Optional[Dict[str, Any]]:
        """Delete a comment (soft delete, only by the author)."""
        # Get comment
        comment_result = await self.db.execute(
            select(VideoComment).where(
                and_(
                    VideoComment.id == comment_id,
                    VideoComment.video_id == video_id,
                    VideoComment.is_deleted == False
                )
            )
        )
        comment = comment_result.scalar_one_or_none()
        
        if not comment:
            return None
        
        # Check if user is the author
        if comment.user_id != user_id:
            return {"error": "unauthorized"}
        
        # Soft delete the comment
        comment.is_deleted = True
        comment.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        return {
            "id": str(comment.id),
            "deleted": True,
            "message": "Comment deleted successfully"
        }
    
    async def get_comment_stats(self, video_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get comment statistics for a video."""
        # Check if video exists
        video_result = await self.db.execute(
            select(Video).where(Video.id == video_id)
        )
        video = video_result.scalar_one_or_none()
        
        if not video:
            return None
        
        # Get total comment count (including replies)
        total_count_result = await self.db.execute(
            select(func.count(VideoComment.id)).where(
                and_(
                    VideoComment.video_id == video_id,
                    VideoComment.is_deleted == False
                )
            )
        )
        total_count = total_count_result.scalar() or 0
        
        # Get top-level comment count
        top_level_count_result = await self.db.execute(
            select(func.count(VideoComment.id)).where(
                and_(
                    VideoComment.video_id == video_id,
                    VideoComment.parent_comment_id.is_(None),
                    VideoComment.is_deleted == False
                )
            )
        )
        top_level_count = top_level_count_result.scalar() or 0
        
        return {
            "video_id": str(video_id),
            "total_comments": total_count,
            "top_level_comments": top_level_count,
            "replies": total_count - top_level_count
        }
    
    async def _get_reply_count(self, comment_id: uuid.UUID) -> int:
        """Get the number of replies to a comment."""
        count_result = await self.db.execute(
            select(func.count(VideoComment.id)).where(
                and_(
                    VideoComment.parent_comment_id == comment_id,
                    VideoComment.is_deleted == False
                )
            )
        )
        return count_result.scalar() or 0
    
    def _clean_content(self, content: str) -> str:
        """Clean and validate comment content."""
        if not content or not content.strip():
            return ""
        
        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content.strip())
        
        # Basic length validation
        if len(content) > 2000:
            content = content[:2000]
        
        # Remove potentially harmful content (basic sanitization)
        # In production, you might want more sophisticated content filtering
        content = re.sub(r'<[^>]*>', '', content)  # Remove HTML tags
        
        return content
    
    async def _moderate_content(self, content: str, user_id: uuid.UUID) -> Dict[str, Any]:
        """Basic content moderation."""
        # Simple spam detection
        if len(content) < 1:
            return {"allowed": False, "reason": "Comment too short"}
        
        # Check for excessive repetition
        words = content.lower().split()
        if len(words) > 5:
            unique_words = set(words)
            if len(unique_words) / len(words) < 0.3:  # Less than 30% unique words
                return {"allowed": False, "reason": "Excessive repetition detected"}
        
        # Check for excessive caps
        if len(content) > 10 and sum(1 for c in content if c.isupper()) / len(content) > 0.7:
            return {"allowed": False, "reason": "Excessive capitalization"}
        
        # Basic profanity filter (you would expand this list)
        profanity_words = ["spam", "scam"]  # Minimal list for demo
        content_lower = content.lower()
        for word in profanity_words:
            if word in content_lower:
                return {"allowed": False, "reason": "Inappropriate content detected"}
        
        # Rate limiting could be implemented here
        # Check if user has posted too many comments recently
        
        return {"allowed": True, "reason": "Content approved"}