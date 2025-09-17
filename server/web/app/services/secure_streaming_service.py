"""
Secure Streaming Service

Handles secure video streaming with signed URLs, access tokens, and session validation.
"""
import uuid
import hmac
import hashlib
import base64
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from urllib.parse import urlencode, parse_qs, urlparse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from ..models import Video, VideoVisibility, User, ViewSession, TranscodingJob
from .base_service import BaseService
from .video_access_control_service import VideoAccessControlService


class SecureStreamingService(BaseService):
    """Service for secure video streaming with access control"""
    
    def __init__(self):
        super().__init__()
        # In production, this should be loaded from environment variables
        self.signing_key = "your-secret-signing-key-change-in-production"
        self.token_expiry_hours = 2
        self.max_concurrent_sessions = 5
    
    async def generate_streaming_manifest(
        self,
        video_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        quality_preference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a secure streaming manifest with signed URLs for video access
        
        Args:
            video_id: Video ID to stream
            user_id: User requesting access
            ip_address: Client IP address
            user_agent: Client user agent
            quality_preference: Preferred quality (optional)
            
        Returns:
            Streaming manifest with signed URLs and access tokens
        """
        # Check video access permissions
        access_control = VideoAccessControlService()
        access_result = await access_control.check_video_access(
            video_id=video_id,
            user_id=user_id,
            ip_address=ip_address
        )
        
        if not access_result["has_access"]:
            return {
                "success": False,
                "error": access_result["reason"],
                "message": access_result["message"]
            }
        
        async with self.get_db_session() as db:
            # Get video with transcoding jobs
            stmt = select(Video).options(
                selectinload(Video.transcoding_jobs)
            ).where(Video.id == video_id)
            
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video:
                return {
                    "success": False,
                    "error": "video_not_found",
                    "message": "Video not found"
                }
            
            # Get available quality options
            available_qualities = await self._get_available_qualities(video)
            
            if not available_qualities:
                return {
                    "success": False,
                    "error": "no_streams_available",
                    "message": "No streams available for this video"
                }
            
            # Create streaming session
            session_token = await self._create_streaming_session(
                video_id=video_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            # Generate signed URLs for each quality
            signed_streams = {}
            for quality in available_qualities:
                signed_url = await self._generate_signed_streaming_url(
                    video_id=video_id,
                    quality=quality["preset"],
                    session_token=session_token,
                    user_id=user_id
                )
                
                signed_streams[quality["preset"]] = {
                    "url": signed_url,
                    "resolution": quality["resolution"],
                    "bitrate": quality["bitrate"],
                    "framerate": quality["framerate"]
                }
            
            # Determine recommended quality
            recommended_quality = self._select_recommended_quality(
                available_qualities, 
                quality_preference
            )
            
            return {
                "success": True,
                "video_id": str(video_id),
                "session_token": session_token,
                "streams": signed_streams,
                "recommended_quality": recommended_quality,
                "expires_at": (datetime.utcnow() + timedelta(hours=self.token_expiry_hours)).isoformat(),
                "video_info": {
                    "title": video.title,
                    "duration": video.duration_seconds,
                    "thumbnail_url": self._get_thumbnail_url(video)
                }
            }
    
    async def validate_streaming_access(
        self,
        video_id: uuid.UUID,
        quality: str,
        session_token: str,
        user_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate access to a specific video stream
        
        Args:
            video_id: Video ID being accessed
            quality: Quality preset being requested
            session_token: Session token from manifest
            user_id: User making the request
            ip_address: Client IP address
            
        Returns:
            Validation result with access decision
        """
        async with self.get_db_session() as db:
            # Find the streaming session
            stmt = select(ViewSession).where(
                and_(
                    ViewSession.video_id == video_id,
                    ViewSession.session_token == session_token
                )
            )
            
            result = await db.execute(stmt)
            session = result.scalar_one_or_none()
            
            if not session:
                return {
                    "valid": False,
                    "error": "invalid_session",
                    "message": "Invalid or expired session token"
                }
            
            # Check session expiry (sessions expire after token_expiry_hours)
            session_age = datetime.utcnow() - session.started_at
            if session_age > timedelta(hours=self.token_expiry_hours):
                return {
                    "valid": False,
                    "error": "session_expired",
                    "message": "Streaming session has expired"
                }
            
            # Validate user matches session (if authenticated)
            if user_id and session.user_id and user_id != session.user_id:
                return {
                    "valid": False,
                    "error": "user_mismatch",
                    "message": "User does not match session"
                }
            
            # Validate IP address (optional security measure)
            if ip_address and session.ip_address_hash:
                expected_hash = self._hash_ip_address(ip_address)
                if expected_hash != session.ip_address_hash:
                    # Log potential security issue but don't block (IP can change)
                    await self._log_security_event(
                        "ip_address_mismatch",
                        video_id,
                        user_id,
                        {"expected": session.ip_address_hash, "actual": expected_hash}
                    )
            
            # Update session heartbeat
            session.last_heartbeat = datetime.utcnow()
            await db.commit()
            
            return {
                "valid": True,
                "session_id": str(session.id),
                "video_id": str(video_id),
                "quality": quality
            }
    
    async def generate_signed_url(
        self,
        video_id: uuid.UUID,
        quality: str,
        session_token: str,
        expires_in_minutes: int = 60
    ) -> str:
        """
        Generate a signed URL for direct video access
        
        Args:
            video_id: Video ID
            quality: Quality preset
            session_token: Valid session token
            expires_in_minutes: URL expiration time
            
        Returns:
            Signed URL for video access
        """
        expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
        
        # Create payload for signing
        payload = {
            "video_id": str(video_id),
            "quality": quality,
            "session_token": session_token,
            "expires_at": int(expires_at.timestamp())
        }
        
        # Generate signature
        signature = self._generate_signature(payload)
        
        # Build signed URL
        base_url = f"/api/stream/{video_id}/{quality}"
        query_params = {
            "token": session_token,
            "expires": int(expires_at.timestamp()),
            "signature": signature
        }
        
        return f"{base_url}?{urlencode(query_params)}"
    
    async def validate_signed_url(
        self,
        video_id: uuid.UUID,
        quality: str,
        token: str,
        expires: int,
        signature: str
    ) -> Dict[str, Any]:
        """
        Validate a signed streaming URL
        
        Args:
            video_id: Video ID from URL
            quality: Quality from URL
            token: Session token from URL
            expires: Expiration timestamp from URL
            signature: URL signature
            
        Returns:
            Validation result
        """
        # Check expiration
        if datetime.utcnow().timestamp() > expires:
            return {
                "valid": False,
                "error": "url_expired",
                "message": "Signed URL has expired"
            }
        
        # Recreate payload and verify signature
        payload = {
            "video_id": str(video_id),
            "quality": quality,
            "session_token": token,
            "expires_at": expires
        }
        
        expected_signature = self._generate_signature(payload)
        
        if not hmac.compare_digest(signature, expected_signature):
            return {
                "valid": False,
                "error": "invalid_signature",
                "message": "Invalid URL signature"
            }
        
        # Validate the session token
        session_validation = await self.validate_streaming_access(
            video_id=video_id,
            quality=quality,
            session_token=token
        )
        
        return session_validation
    
    async def revoke_streaming_session(
        self,
        session_token: str,
        user_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Revoke a streaming session (logout/security)
        
        Args:
            session_token: Session token to revoke
            user_id: User requesting revocation (for authorization)
            
        Returns:
            Revocation result
        """
        async with self.get_db_session() as db:
            stmt = select(ViewSession).where(
                ViewSession.session_token == session_token
            )
            
            result = await db.execute(stmt)
            session = result.scalar_one_or_none()
            
            if not session:
                return {
                    "success": False,
                    "error": "session_not_found",
                    "message": "Session not found"
                }
            
            # Check authorization (user can only revoke their own sessions)
            if user_id and session.user_id and user_id != session.user_id:
                return {
                    "success": False,
                    "error": "unauthorized",
                    "message": "Cannot revoke another user's session"
                }
            
            # Mark session as ended
            session.ended_at = datetime.utcnow()
            await db.commit()
            
            return {
                "success": True,
                "message": "Streaming session revoked"
            }
    
    async def list_active_sessions(
        self,
        user_id: uuid.UUID
    ) -> List[Dict[str, Any]]:
        """
        List active streaming sessions for a user
        
        Args:
            user_id: User ID to list sessions for
            
        Returns:
            List of active sessions
        """
        async with self.get_db_session() as db:
            # Get active sessions (not ended and recent heartbeat)
            cutoff_time = datetime.utcnow() - timedelta(hours=self.token_expiry_hours)
            
            stmt = select(ViewSession).options(
                selectinload(ViewSession.video)
            ).where(
                and_(
                    ViewSession.user_id == user_id,
                    ViewSession.ended_at.is_(None),
                    ViewSession.last_heartbeat > cutoff_time
                )
            )
            
            result = await db.execute(stmt)
            sessions = result.scalars().all()
            
            session_list = []
            for session in sessions:
                session_list.append({
                    "session_token": session.session_token,
                    "video_id": str(session.video_id),
                    "video_title": session.video.title if session.video else "Unknown",
                    "started_at": session.started_at.isoformat(),
                    "last_heartbeat": session.last_heartbeat.isoformat(),
                    "current_position": session.current_position_seconds,
                    "watch_time": session.total_watch_time_seconds
                })
            
            return session_list
    
    async def _get_available_qualities(self, video: Video) -> List[Dict[str, Any]]:
        """Get available quality options for a video"""
        qualities = []
        
        for job in video.transcoding_jobs:
            if job.status == "completed" and job.hls_manifest_s3_key:
                qualities.append({
                    "preset": job.quality_preset,
                    "resolution": job.target_resolution,
                    "bitrate": job.target_bitrate,
                    "framerate": job.target_framerate
                })
        
        # Sort by quality (resolution and framerate)
        qualities.sort(key=lambda x: (
            int(x["resolution"].split("x")[1]) if "x" in x["resolution"] else 0,
            x["framerate"]
        ), reverse=True)
        
        return qualities
    
    async def _create_streaming_session(
        self,
        video_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        ip_address: Optional[str],
        user_agent: Optional[str]
    ) -> str:
        """Create a new streaming session"""
        async with self.get_db_session() as db:
            # Check for existing active sessions (limit concurrent sessions)
            if user_id:
                active_sessions_stmt = select(ViewSession).where(
                    and_(
                        ViewSession.user_id == user_id,
                        ViewSession.ended_at.is_(None),
                        ViewSession.last_heartbeat > datetime.utcnow() - timedelta(hours=1)
                    )
                )
                
                result = await db.execute(active_sessions_stmt)
                active_sessions = result.scalars().all()
                
                # End oldest sessions if over limit
                if len(active_sessions) >= self.max_concurrent_sessions:
                    oldest_sessions = sorted(active_sessions, key=lambda s: s.last_heartbeat)
                    for session in oldest_sessions[:-self.max_concurrent_sessions + 1]:
                        session.ended_at = datetime.utcnow()
            
            # Create new session
            session_token = self._generate_session_token()
            
            session = ViewSession(
                video_id=video_id,
                user_id=user_id,
                session_token=session_token,
                ip_address_hash=self._hash_ip_address(ip_address) if ip_address else None,
                user_agent_hash=self._hash_user_agent(user_agent) if user_agent else None,
                started_at=datetime.utcnow(),
                last_heartbeat=datetime.utcnow()
            )
            
            db.add(session)
            await db.commit()
            
            return session_token
    
    async def _generate_signed_streaming_url(
        self,
        video_id: uuid.UUID,
        quality: str,
        session_token: str,
        user_id: Optional[uuid.UUID]
    ) -> str:
        """Generate signed URL for a specific quality stream"""
        return await self.generate_signed_url(
            video_id=video_id,
            quality=quality,
            session_token=session_token,
            expires_in_minutes=120  # 2 hours
        )
    
    def _select_recommended_quality(
        self,
        available_qualities: List[Dict[str, Any]],
        preference: Optional[str]
    ) -> str:
        """Select recommended quality based on preference and availability"""
        if not available_qualities:
            return None
        
        # If preference specified and available, use it
        if preference:
            for quality in available_qualities:
                if quality["preset"] == preference:
                    return preference
        
        # Default to 720p if available, otherwise highest available
        for quality in available_qualities:
            if "720p" in quality["preset"]:
                return quality["preset"]
        
        return available_qualities[0]["preset"]
    
    def _generate_session_token(self) -> str:
        """Generate a unique session token"""
        return base64.urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip('=')
    
    def _generate_signature(self, payload: Dict[str, Any]) -> str:
        """Generate HMAC signature for payload"""
        message = json.dumps(payload, sort_keys=True).encode()
        signature = hmac.new(
            self.signing_key.encode(),
            message,
            hashlib.sha256
        ).digest()
        return base64.urlsafe_b64encode(signature).decode().rstrip('=')
    
    def _hash_ip_address(self, ip_address: str) -> str:
        """Hash IP address for privacy"""
        return hashlib.sha256(ip_address.encode()).hexdigest()[:16]
    
    def _hash_user_agent(self, user_agent: str) -> str:
        """Hash user agent for privacy"""
        return hashlib.sha256(user_agent.encode()).hexdigest()[:16]
    
    def _get_thumbnail_url(self, video: Video) -> Optional[str]:
        """Get thumbnail URL for video"""
        if video.thumbnail_s3_key:
            # In production, this would be a CDN URL
            return f"/api/thumbnails/{video.id}"
        return None
    
    async def _log_security_event(
        self,
        event_type: str,
        video_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        details: Dict[str, Any]
    ) -> None:
        """Log security-related events"""
        async with self.get_db_session() as db:
            from ..models import AnalyticsEvent
            
            event = AnalyticsEvent(
                event_type=f"security_{event_type}",
                user_id=user_id,
                content_id=video_id,
                timestamp=datetime.utcnow(),
                data=details
            )
            
            db.add(event)
            await db.commit()