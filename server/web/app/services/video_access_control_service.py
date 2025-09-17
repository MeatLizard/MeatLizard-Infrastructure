"""
Video Access Control Service

Handles video visibility, permissions, and authorization for the video platform.
"""
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from ..models import Video, VideoVisibility, User, Channel, VideoPlaylist, VideoPermission
from .base_service import BaseService


class VideoAccessControlService(BaseService):
    """Service for managing video access control and permissions"""
    
    async def check_video_access(
        self, 
        video_id: uuid.UUID, 
        user_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if a user has access to view a video
        
        Args:
            video_id: Video ID to check access for
            user_id: User ID requesting access (None for anonymous)
            ip_address: IP address for logging and restrictions
            
        Returns:
            Dict with access status and details
        """
        async with self.get_db_session() as db:
            # Get video with creator and channel info
            stmt = select(Video).options(
                selectinload(Video.creator),
                selectinload(Video.channel)
            ).where(Video.id == video_id)
            
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video:
                return {
                    "has_access": False,
                    "reason": "video_not_found",
                    "message": "Video not found"
                }
            
            # Check if video is ready for viewing
            if video.status != "ready":
                # Only creator can view non-ready videos
                if user_id != video.creator_id:
                    return {
                        "has_access": False,
                        "reason": "video_not_ready",
                        "message": "Video is still processing"
                    }
            
            # Check visibility-based access
            access_result = await self._check_visibility_access(video, user_id)
            
            # Log access attempt
            await self._log_access_attempt(video_id, user_id, ip_address, access_result["has_access"])
            
            return access_result
    
    async def _check_visibility_access(
        self, 
        video: Video, 
        user_id: Optional[uuid.UUID]
    ) -> Dict[str, Any]:
        """Check access based on video visibility settings"""
        
        if video.visibility == VideoVisibility.public:
            return {
                "has_access": True,
                "reason": "public_video",
                "message": "Video is publicly accessible"
            }
        
        elif video.visibility == VideoVisibility.unlisted:
            return {
                "has_access": True,
                "reason": "unlisted_video",
                "message": "Video is accessible via direct link"
            }
        
        elif video.visibility == VideoVisibility.private:
            if not user_id:
                return {
                    "has_access": False,
                    "reason": "authentication_required",
                    "message": "Authentication required for private video"
                }
            
            # Check if user is the creator
            if user_id == video.creator_id:
                return {
                    "has_access": True,
                    "reason": "video_creator",
                    "message": "Access granted as video creator"
                }
            
            # Check if user has explicit permission
            has_permission = await self._check_explicit_permission(video.id, user_id)
            if has_permission:
                return {
                    "has_access": True,
                    "reason": "explicit_permission",
                    "message": "Access granted via explicit permission"
                }
            
            # Check channel-level permissions if video is in a channel
            if video.channel_id:
                has_channel_access = await self._check_channel_access(video.channel_id, user_id)
                if has_channel_access:
                    return {
                        "has_access": True,
                        "reason": "channel_permission",
                        "message": "Access granted via channel permissions"
                    }
            
            return {
                "has_access": False,
                "reason": "insufficient_permissions",
                "message": "Insufficient permissions to view private video"
            }
        
        return {
            "has_access": False,
            "reason": "unknown_visibility",
            "message": "Unknown video visibility setting"
        }
    
    async def _check_explicit_permission(
        self, 
        video_id: uuid.UUID, 
        user_id: uuid.UUID
    ) -> bool:
        """Check if user has explicit permission to view video"""
        async with self.get_db_session() as db:
            # Check video permissions table (to be created)
            stmt = select(VideoPermission).where(
                and_(
                    VideoPermission.video_id == video_id,
                    VideoPermission.user_id == user_id,
                    VideoPermission.permission_type == "view",
                    or_(
                        VideoPermission.expires_at.is_(None),
                        VideoPermission.expires_at > datetime.utcnow()
                    )
                )
            )
            
            result = await db.execute(stmt)
            permission = result.scalar_one_or_none()
            
            return permission is not None
    
    async def _check_channel_access(
        self, 
        channel_id: uuid.UUID, 
        user_id: uuid.UUID
    ) -> bool:
        """Check if user has access to channel content"""
        async with self.get_db_session() as db:
            # Get channel info
            stmt = select(Channel).where(Channel.id == channel_id)
            result = await db.execute(stmt)
            channel = result.scalar_one_or_none()
            
            if not channel:
                return False
            
            # Channel creator has access to all channel content
            if channel.creator_id == user_id:
                return True
            
            # Check channel permissions (to be implemented)
            # For now, only channel creator has access to private channel content
            return False
    
    async def grant_video_permission(
        self,
        video_id: uuid.UUID,
        user_id: uuid.UUID,
        granted_by: uuid.UUID,
        permission_type: str = "view",
        expires_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Grant explicit permission to a user for a video"""
        async with self.get_db_session() as db:
            # Verify the granter has permission to grant access
            video_access = await self.check_video_access(video_id, granted_by)
            if not video_access["has_access"]:
                return {
                    "success": False,
                    "message": "Insufficient permissions to grant access"
                }
            
            # Check if user is video creator or has admin permissions
            stmt = select(Video).where(Video.id == video_id)
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video or video.creator_id != granted_by:
                # TODO: Add admin role check here
                return {
                    "success": False,
                    "message": "Only video creator can grant permissions"
                }
            
            # Create or update permission
            permission = VideoPermission(
                video_id=video_id,
                user_id=user_id,
                permission_type=permission_type,
                granted_by=granted_by,
                expires_at=expires_at,
                created_at=datetime.utcnow()
            )
            
            db.add(permission)
            await db.commit()
            
            return {
                "success": True,
                "message": "Permission granted successfully",
                "permission_id": permission.id
            }
    
    async def revoke_video_permission(
        self,
        video_id: uuid.UUID,
        user_id: uuid.UUID,
        revoked_by: uuid.UUID
    ) -> Dict[str, Any]:
        """Revoke explicit permission from a user for a video"""
        async with self.get_db_session() as db:
            # Verify the revoker has permission to revoke access
            stmt = select(Video).where(Video.id == video_id)
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video or video.creator_id != revoked_by:
                # TODO: Add admin role check here
                return {
                    "success": False,
                    "message": "Only video creator can revoke permissions"
                }
            
            # Find and delete permission
            stmt = select(VideoPermission).where(
                and_(
                    VideoPermission.video_id == video_id,
                    VideoPermission.user_id == user_id
                )
            )
            
            result = await db.execute(stmt)
            permission = result.scalar_one_or_none()
            
            if permission:
                await db.delete(permission)
                await db.commit()
                
                return {
                    "success": True,
                    "message": "Permission revoked successfully"
                }
            else:
                return {
                    "success": False,
                    "message": "Permission not found"
                }
    
    async def update_video_visibility(
        self,
        video_id: uuid.UUID,
        new_visibility: VideoVisibility,
        updated_by: uuid.UUID
    ) -> Dict[str, Any]:
        """Update video visibility setting"""
        async with self.get_db_session() as db:
            # Get video and verify permissions
            stmt = select(Video).where(Video.id == video_id)
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video:
                return {
                    "success": False,
                    "message": "Video not found"
                }
            
            # Check if user can modify video
            if video.creator_id != updated_by:
                # TODO: Add admin role check here
                return {
                    "success": False,
                    "message": "Only video creator can change visibility"
                }
            
            # Update visibility
            old_visibility = video.visibility
            video.visibility = new_visibility
            video.updated_at = datetime.utcnow()
            
            await db.commit()
            
            # Log visibility change
            await self._log_visibility_change(video_id, old_visibility, new_visibility, updated_by)
            
            return {
                "success": True,
                "message": "Video visibility updated successfully",
                "old_visibility": old_visibility.value,
                "new_visibility": new_visibility.value
            }
    
    async def list_video_permissions(
        self,
        video_id: uuid.UUID,
        requested_by: uuid.UUID
    ) -> Dict[str, Any]:
        """List all permissions for a video"""
        async with self.get_db_session() as db:
            # Verify requester has permission to view permissions
            stmt = select(Video).where(Video.id == video_id)
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video or video.creator_id != requested_by:
                # TODO: Add admin role check here
                return {
                    "success": False,
                    "message": "Insufficient permissions to view video permissions"
                }
            
            # Get all permissions for the video
            stmt = select(VideoPermission).options(
                selectinload(VideoPermission.user),
                selectinload(VideoPermission.granted_by_user)
            ).where(VideoPermission.video_id == video_id)
            
            result = await db.execute(stmt)
            permissions = result.scalars().all()
            
            permission_list = []
            for perm in permissions:
                permission_list.append({
                    "id": perm.id,
                    "user_id": perm.user_id,
                    "user_name": perm.user.display_label if perm.user else "Unknown",
                    "permission_type": perm.permission_type,
                    "granted_by": perm.granted_by,
                    "granted_by_name": perm.granted_by_user.display_label if perm.granted_by_user else "Unknown",
                    "created_at": perm.created_at.isoformat(),
                    "expires_at": perm.expires_at.isoformat() if perm.expires_at else None
                })
            
            return {
                "success": True,
                "permissions": permission_list,
                "total_count": len(permission_list)
            }
    
    async def _log_access_attempt(
        self,
        video_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        ip_address: Optional[str],
        access_granted: bool
    ) -> None:
        """Log video access attempt for security and analytics"""
        # This would typically go to a separate access log table
        # For now, we'll use the existing analytics events table
        async with self.get_db_session() as db:
            from ..models import AnalyticsEvent
            
            event = AnalyticsEvent(
                event_type="video_access_attempt",
                user_id=user_id,
                content_id=video_id,
                timestamp=datetime.utcnow(),
                data={
                    "access_granted": access_granted,
                    "ip_address_hash": self._hash_ip_address(ip_address) if ip_address else None
                }
            )
            
            db.add(event)
            await db.commit()
    
    async def _log_visibility_change(
        self,
        video_id: uuid.UUID,
        old_visibility: VideoVisibility,
        new_visibility: VideoVisibility,
        changed_by: uuid.UUID
    ) -> None:
        """Log video visibility changes for audit trail"""
        async with self.get_db_session() as db:
            from ..models import AnalyticsEvent
            
            event = AnalyticsEvent(
                event_type="video_visibility_change",
                user_id=changed_by,
                content_id=video_id,
                timestamp=datetime.utcnow(),
                data={
                    "old_visibility": old_visibility.value,
                    "new_visibility": new_visibility.value
                }
            )
            
            db.add(event)
            await db.commit()
    
    def _hash_ip_address(self, ip_address: str) -> str:
        """Hash IP address for privacy while maintaining uniqueness"""
        import hashlib
        return hashlib.sha256(ip_address.encode()).hexdigest()[:16]


