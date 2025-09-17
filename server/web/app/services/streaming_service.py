
"""
Video streaming service with access control, signed URLs, and quality recommendations.
"""
import hashlib
import hmac
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from server.web.app.models import Video, VideoStatus, VideoVisibility, ViewSession, User, TranscodingJob, TranscodingStatus
from server.web.app.services.base_service import BaseService
from server.web.app.services.video_s3_service import VideoS3Service
from server.web.app.services.hls_service import HLSService
from server.web.app.config import settings

logger = logging.getLogger(__name__)

class StreamingService(BaseService):
    """Service for video streaming with access control and quality management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.s3_service = VideoS3Service(settings.S3_BUCKET_NAME)
        self.hls_service = HLSService(settings.S3_BUCKET_NAME)
    
    async def check_video_access(self, video_id: str, user_id: Optional[str] = None, 
                               ip_address: Optional[str] = None) -> bool:
        """
        Check if user has permission to access video.
        
        Args:
            video_id: Video identifier
            user_id: User identifier (optional for anonymous access)
            ip_address: Client IP address for rate limiting
        
        Returns:
            True if access is allowed
        
        Raises:
            HTTPException: If access is denied
        """
        try:
            # Get video
            video = await self.db.get(Video, video_id)
            if not video:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Video not found"
                )
            
            # Check video status
            if video.status != VideoStatus.ready:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Video is not ready for streaming (status: {video.status.value})"
                )
            
            # Check visibility permissions
            if video.visibility == VideoVisibility.public:
                return True
            elif video.visibility == VideoVisibility.unlisted:
                return True  # Anyone with link can access
            elif video.visibility == VideoVisibility.private:
                if not user_id:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required for private video"
                    )
                
                # Check if user is creator or has explicit permission
                if user_id == str(video.creator_id):
                    return True
                
                # TODO: Implement explicit permissions for private videos
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to private video"
                )
            
            return False
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking video access for {video_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to check video access"
            )
    
    def generate_signed_streaming_url(self, video_id: str, quality: Optional[str] = None, 
                                    expires_in: int = 7200) -> str:
        """
        Generate time-limited signed URL for video streaming.
        
        Args:
            video_id: Video identifier
            quality: Specific quality preset, or None for master playlist
            expires_in: URL expiration time in seconds (default: 2 hours)
        
        Returns:
            Signed streaming URL
        """
        try:
            expires = int(time.time()) + expires_in
            
            # Create message to sign
            if quality:
                resource = f"video/{video_id}/quality/{quality}"
            else:
                resource = f"video/{video_id}/master"
            
            message = f"{resource}:{expires}".encode('utf-8')
            signature = hmac.new(
                settings.SECRET_KEY.encode('utf-8'), 
                message, 
                hashlib.sha256
            ).hexdigest()
            
            # Get base streaming URL
            base_url = self.hls_service.get_streaming_url(video_id, quality)
            
            # Add signature parameters
            separator = "&" if "?" in base_url else "?"
            signed_url = f"{base_url}{separator}expires={expires}&signature={signature}"
            
            return signed_url
            
        except Exception as e:
            logger.error(f"Failed to generate signed URL for video {video_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate signed streaming URL"
            )
    
    def validate_signed_url(self, video_id: str, quality: Optional[str], 
                          expires: int, signature: str) -> bool:
        """
        Validate signed streaming URL.
        
        Args:
            video_id: Video identifier
            quality: Quality preset or None for master
            expires: Expiration timestamp
            signature: URL signature
        
        Returns:
            True if signature is valid
        
        Raises:
            HTTPException: If signature is invalid or expired
        """
        try:
            # Check expiration
            if expires < time.time():
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Streaming URL has expired"
                )
            
            # Recreate message and verify signature
            if quality:
                resource = f"video/{video_id}/quality/{quality}"
            else:
                resource = f"video/{video_id}/master"
            
            message = f"{resource}:{expires}".encode('utf-8')
            expected_signature = hmac.new(
                settings.SECRET_KEY.encode('utf-8'),
                message,
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(expected_signature, signature):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid streaming URL signature"
                )
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error validating signed URL for video {video_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to validate streaming URL"
            )
    
    async def get_quality_recommendation(self, video_id: str, bandwidth_kbps: Optional[int] = None,
                                       device_type: Optional[str] = None) -> Dict[str, any]:
        """
        Recommend optimal quality based on bandwidth and device capabilities.
        
        Args:
            video_id: Video identifier
            bandwidth_kbps: Available bandwidth in kbps
            device_type: Device type (mobile, tablet, desktop)
        
        Returns:
            Dictionary with recommended quality and alternatives
        """
        try:
            # Get available qualities
            qualities = await self.hls_service.get_available_qualities(video_id)
            if not qualities:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No qualities available for video"
                )
            
            # Sort qualities by bitrate (ascending)
            qualities.sort(key=lambda q: q.get("height", 0))
            
            recommended_quality = None
            
            if bandwidth_kbps:
                # Recommend quality based on bandwidth
                # Use 80% of available bandwidth to account for fluctuations
                target_bitrate = bandwidth_kbps * 0.8
                
                for quality in qualities:
                    # Estimate bitrate based on resolution (rough calculation)
                    height = quality.get("height", 720)
                    framerate = quality.get("framerate", 30)
                    
                    # Rough bitrate estimation (kbps)
                    if height <= 480:
                        estimated_bitrate = 1000 * (framerate / 30)
                    elif height <= 720:
                        estimated_bitrate = 2500 * (framerate / 30)
                    elif height <= 1080:
                        estimated_bitrate = 5000 * (framerate / 30)
                    else:
                        estimated_bitrate = 8000 * (framerate / 30)
                    
                    if estimated_bitrate <= target_bitrate:
                        recommended_quality = quality
                    else:
                        break
            
            # Device-based recommendations
            if device_type == "mobile" and not recommended_quality:
                # Prefer 720p or lower for mobile
                for quality in qualities:
                    if quality.get("height", 0) <= 720:
                        recommended_quality = quality
            elif device_type == "tablet" and not recommended_quality:
                # Prefer 1080p or lower for tablets
                for quality in qualities:
                    if quality.get("height", 0) <= 1080:
                        recommended_quality = quality
            
            # Default to highest available quality if no specific recommendation
            if not recommended_quality:
                recommended_quality = qualities[-1] if qualities else None
            
            return {
                "recommended": recommended_quality,
                "available_qualities": qualities,
                "bandwidth_kbps": bandwidth_kbps,
                "device_type": device_type,
                "auto_switch_enabled": True
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get quality recommendation for video {video_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get quality recommendation"
            )
    
    async def create_viewing_session(self, video_id: str, user_id: Optional[str] = None,
                                   ip_address: Optional[str] = None, 
                                   user_agent: Optional[str] = None) -> ViewSession:
        """
        Create a new viewing session for tracking playback.
        
        Args:
            video_id: Video identifier
            user_id: User identifier (optional for anonymous viewing)
            ip_address: Client IP address
            user_agent: Client user agent string
        
        Returns:
            ViewSession object
        """
        try:
            # Generate session token
            session_token = hashlib.sha256(
                f"{video_id}:{user_id}:{time.time()}".encode()
            ).hexdigest()[:32]
            
            # Hash sensitive data
            ip_hash = None
            if ip_address:
                ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()
            
            user_agent_hash = None
            if user_agent:
                user_agent_hash = hashlib.sha256(user_agent.encode()).hexdigest()
            
            # Create viewing session
            view_session = ViewSession(
                video_id=video_id,
                user_id=user_id,
                session_token=session_token,
                ip_address_hash=ip_hash,
                user_agent_hash=user_agent_hash,
                started_at=datetime.utcnow(),
                last_heartbeat=datetime.utcnow()
            )
            
            self.db.add(view_session)
            await self.db.commit()
            await self.db.refresh(view_session)
            
            logger.info(f"Created viewing session {session_token} for video {video_id}")
            return view_session
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create viewing session for video {video_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create viewing session"
            )
    
    async def get_streaming_manifest(self, video_id: str, user_id: Optional[str] = None,
                                   quality: Optional[str] = None, 
                                   session_token: Optional[str] = None) -> Dict[str, any]:
        """
        Get streaming manifest with access control and signed URLs.
        
        Args:
            video_id: Video identifier
            user_id: User identifier for access control
            quality: Specific quality preset
            session_token: Viewing session token
        
        Returns:
            Streaming manifest with URLs and metadata
        """
        try:
            # Check access permissions
            await self.check_video_access(video_id, user_id)
            
            # Get video details
            video = await self.db.get(Video, video_id)
            
            # Get available qualities
            qualities = await self.hls_service.get_available_qualities(video_id)
            
            # Generate signed URLs for each quality
            signed_qualities = []
            for q in qualities:
                quality_preset = q["quality_preset"]
                signed_url = self.generate_signed_streaming_url(video_id, quality_preset)
                q["signed_url"] = signed_url
                signed_qualities.append(q)
            
            # Generate master playlist URL
            master_url = self.generate_signed_streaming_url(video_id)
            
            return {
                "video_id": video_id,
                "title": video.title,
                "description": video.description,
                "duration": video.duration_seconds,
                "master_playlist_url": master_url,
                "qualities": signed_qualities,
                "session_token": session_token,
                "created_at": datetime.utcnow().isoformat()
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get streaming manifest for video {video_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get streaming manifest"
            )
    
    async def get_user_resume_position(self, video_id: str, user_id: str) -> Dict[str, any]:
        """
        Get resume position for a user and video.
        
        Args:
            video_id: Video identifier
            user_id: User identifier
        
        Returns:
            Resume position information
        """
        try:
            # Get most recent viewing session
            result = await self.db.execute(
                select(ViewSession)
                .where(
                    ViewSession.video_id == video_id,
                    ViewSession.user_id == user_id
                )
                .order_by(ViewSession.last_heartbeat.desc())
                .limit(1)
            )
            
            latest_session = result.scalar_one_or_none()
            
            if not latest_session:
                return {
                    "has_resume_position": False,
                    "resume_position": 0,
                    "completion_percentage": 0
                }
            
            # Only offer resume if meaningful progress was made
            can_resume = (
                latest_session.current_position_seconds > 30 and 
                latest_session.completion_percentage < 95
            )
            
            return {
                "has_resume_position": can_resume,
                "resume_position": latest_session.current_position_seconds if can_resume else 0,
                "completion_percentage": latest_session.completion_percentage,
                "last_watched": latest_session.last_heartbeat.isoformat(),
                "session_id": str(latest_session.id)
            }
            
        except Exception as e:
            logger.error(f"Failed to get resume position for video {video_id}, user {user_id}: {e}")
            return {
                "has_resume_position": False,
                "resume_position": 0,
                "completion_percentage": 0
            }
    
    async def update_viewing_progress(self, session_token: str, video_id: str, 
                                   progress_data: Dict[str, any]) -> ViewSession:
        """
        Update viewing progress for a session.
        
        Args:
            session_token: Session token
            video_id: Video identifier
            progress_data: Progress information
        
        Returns:
            Updated ViewSession
        """
        try:
            # Find viewing session
            result = await self.db.execute(
                select(ViewSession).where(
                    ViewSession.session_token == session_token,
                    ViewSession.video_id == video_id
                )
            )
            view_session = result.scalar_one_or_none()
            
            if not view_session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Viewing session not found"
                )
            
            # Update progress
            current_position = progress_data.get('current_position_seconds', 0)
            completion_percentage = progress_data.get('completion_percentage', 0)
            quality_switches = progress_data.get('quality_switches', view_session.quality_switches)
            buffering_events = progress_data.get('buffering_events', view_session.buffering_events)
            
            # Calculate watch time increment
            time_since_last_update = (datetime.utcnow() - view_session.last_heartbeat).total_seconds()
            watch_time_increment = min(time_since_last_update, 15)  # Cap at 15 seconds
            
            # Update session
            view_session.current_position_seconds = current_position
            view_session.completion_percentage = completion_percentage
            view_session.total_watch_time_seconds += watch_time_increment
            view_session.quality_switches = quality_switches
            view_session.buffering_events = buffering_events
            view_session.last_heartbeat = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(view_session)
            
            return view_session
            
        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update viewing progress: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update viewing progress"
            )
    
    async def end_viewing_session(self, session_token: str, video_id: str, 
                                final_data: Dict[str, any]) -> ViewSession:
        """
        End a viewing session with final statistics.
        
        Args:
            session_token: Session token
            video_id: Video identifier
            final_data: Final viewing statistics
        
        Returns:
            Ended ViewSession
        """
        try:
            # Find viewing session
            result = await self.db.execute(
                select(ViewSession).where(
                    ViewSession.session_token == session_token,
                    ViewSession.video_id == video_id
                )
            )
            view_session = result.scalar_one_or_none()
            
            if not view_session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Viewing session not found"
                )
            
            # Update final statistics
            view_session.current_position_seconds = final_data.get(
                'current_position_seconds', 
                view_session.current_position_seconds
            )
            view_session.completion_percentage = final_data.get(
                'completion_percentage', 
                view_session.completion_percentage
            )
            view_session.quality_switches = final_data.get(
                'quality_switches', 
                view_session.quality_switches
            )
            view_session.buffering_events = final_data.get(
                'buffering_events', 
                view_session.buffering_events
            )
            view_session.ended_at = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(view_session)
            
            logger.info(f"Ended viewing session {session_token} for video {video_id}")
            return view_session
            
        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to end viewing session: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to end viewing session"
            )
