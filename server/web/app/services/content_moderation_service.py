"""
Content Moderation Service

Handles automated content scanning, manual moderation, reporting, and content takedown.
"""
import uuid
import re
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from ..models import Video, VideoComment, User, AnalyticsEvent
from .base_service import BaseService


class ModerationAction(str, Enum):
    """Types of moderation actions"""
    APPROVED = "approved"
    FLAGGED = "flagged"
    HIDDEN = "hidden"
    REMOVED = "removed"
    RESTRICTED = "restricted"
    BANNED = "banned"


class ModerationReason(str, Enum):
    """Reasons for moderation actions"""
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    SPAM = "spam"
    HARASSMENT = "harassment"
    COPYRIGHT_VIOLATION = "copyright_violation"
    VIOLENCE = "violence"
    HATE_SPEECH = "hate_speech"
    ADULT_CONTENT = "adult_content"
    MISLEADING_INFO = "misleading_info"
    PRIVACY_VIOLATION = "privacy_violation"
    OTHER = "other"


class ReportType(str, Enum):
    """Types of content reports"""
    VIDEO = "video"
    COMMENT = "comment"
    USER = "user"
    CHANNEL = "channel"


class ContentModerationService(BaseService):
    """Service for content moderation and safety"""
    
    def __init__(self):
        super().__init__()
        self.profanity_patterns = self._load_profanity_patterns()
        self.spam_patterns = self._load_spam_patterns()
        
    async def scan_video_content(
        self,
        video_id: uuid.UUID,
        scan_metadata: bool = True,
        scan_visual: bool = False,
        scan_audio: bool = False
    ) -> Dict[str, Any]:
        """
        Perform automated content scanning on a video
        
        Args:
            video_id: Video ID to scan
            scan_metadata: Scan title, description, tags
            scan_visual: Scan video frames (requires AI service)
            scan_audio: Scan audio content (requires AI service)
            
        Returns:
            Scan results with risk assessment
        """
        async with self.get_db_session() as db:
            # Get video with metadata
            stmt = select(Video).where(Video.id == video_id)
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video:
                return {
                    "success": False,
                    "error": "video_not_found",
                    "message": "Video not found"
                }
            
            scan_results = {
                "video_id": str(video_id),
                "scan_timestamp": datetime.utcnow().isoformat(),
                "metadata_scan": {},
                "visual_scan": {},
                "audio_scan": {},
                "overall_risk": "low",
                "recommended_action": ModerationAction.APPROVED,
                "flags": []
            }
            
            # Scan metadata (title, description, tags)
            if scan_metadata:
                metadata_results = await self._scan_metadata(video)
                scan_results["metadata_scan"] = metadata_results
                
                if metadata_results["risk_level"] in ["high", "critical"]:
                    scan_results["overall_risk"] = metadata_results["risk_level"]
                    scan_results["recommended_action"] = ModerationAction.FLAGGED
                    scan_results["flags"].extend(metadata_results["flags"])
            
            # Scan visual content (placeholder for AI integration)
            if scan_visual:
                visual_results = await self._scan_visual_content(video)
                scan_results["visual_scan"] = visual_results
                
                if visual_results["risk_level"] in ["high", "critical"]:
                    scan_results["overall_risk"] = "high"
                    scan_results["recommended_action"] = ModerationAction.HIDDEN
                    scan_results["flags"].extend(visual_results["flags"])
            
            # Scan audio content (placeholder for AI integration)
            if scan_audio:
                audio_results = await self._scan_audio_content(video)
                scan_results["audio_scan"] = audio_results
                
                if audio_results["risk_level"] in ["high", "critical"]:
                    scan_results["overall_risk"] = "high"
                    scan_results["recommended_action"] = ModerationAction.HIDDEN
                    scan_results["flags"].extend(audio_results["flags"])
            
            # Store scan results
            await self._store_scan_results(video_id, scan_results)
            
            # Auto-moderate if critical issues found
            if scan_results["overall_risk"] == "critical":
                await self.apply_moderation_action(
                    content_type="video",
                    content_id=video_id,
                    action=ModerationAction.HIDDEN,
                    reason=ModerationReason.INAPPROPRIATE_CONTENT,
                    moderator_id=None,  # Automated action
                    notes="Automatically hidden due to critical content violations"
                )
            
            return scan_results
    
    async def scan_comment_content(
        self,
        comment_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Scan comment content for inappropriate material
        
        Args:
            comment_id: Comment ID to scan
            
        Returns:
            Scan results with moderation recommendation
        """
        async with self.get_db_session() as db:
            # Get comment
            stmt = select(VideoComment).where(VideoComment.id == comment_id)
            result = await db.execute(stmt)
            comment = result.scalar_one_or_none()
            
            if not comment:
                return {
                    "success": False,
                    "error": "comment_not_found",
                    "message": "Comment not found"
                }
            
            # Scan comment text
            text_scan = self._scan_text_content(comment.content)
            
            scan_results = {
                "comment_id": str(comment_id),
                "scan_timestamp": datetime.utcnow().isoformat(),
                "text_scan": text_scan,
                "overall_risk": text_scan["risk_level"],
                "recommended_action": self._get_recommended_action(text_scan["risk_level"]),
                "flags": text_scan["flags"]
            }
            
            # Store scan results
            await self._store_scan_results(comment_id, scan_results, content_type="comment")
            
            # Auto-moderate severe violations
            if scan_results["overall_risk"] == "critical":
                await self.apply_moderation_action(
                    content_type="comment",
                    content_id=comment_id,
                    action=ModerationAction.REMOVED,
                    reason=ModerationReason.INAPPROPRIATE_CONTENT,
                    moderator_id=None,
                    notes="Automatically removed due to severe content violations"
                )
            
            return scan_results
    
    async def submit_content_report(
        self,
        reporter_id: uuid.UUID,
        content_type: ReportType,
        content_id: uuid.UUID,
        reason: ModerationReason,
        description: Optional[str] = None,
        evidence_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Submit a content report from a user
        
        Args:
            reporter_id: User submitting the report
            content_type: Type of content being reported
            content_id: ID of the content being reported
            reason: Reason for the report
            description: Additional description from reporter
            evidence_urls: URLs to evidence (screenshots, etc.)
            
        Returns:
            Report submission result
        """
        async with self.get_db_session() as db:
            # Check if user has already reported this content
            existing_report = await self._check_existing_report(
                reporter_id, content_type, content_id
            )
            
            if existing_report:
                return {
                    "success": False,
                    "error": "already_reported",
                    "message": "You have already reported this content"
                }
            
            # Create content report
            report = ContentReport(
                id=uuid.uuid4(),
                reporter_id=reporter_id,
                content_type=content_type.value,
                content_id=content_id,
                reason=reason.value,
                description=description,
                evidence_urls=evidence_urls or [],
                status="pending",
                created_at=datetime.utcnow()
            )
            
            db.add(report)
            await db.commit()
            
            # Log the report event
            await self._log_moderation_event(
                "content_reported",
                content_id,
                reporter_id,
                {
                    "content_type": content_type.value,
                    "reason": reason.value,
                    "report_id": str(report.id)
                }
            )
            
            # Check if this content has multiple reports (auto-escalate)
            report_count = await self._get_report_count(content_type, content_id)
            if report_count >= 3:  # Threshold for auto-escalation
                await self._escalate_content(content_type, content_id, "multiple_reports")
            
            return {
                "success": True,
                "report_id": str(report.id),
                "message": "Report submitted successfully"
            }
    
    async def apply_moderation_action(
        self,
        content_type: str,
        content_id: uuid.UUID,
        action: ModerationAction,
        reason: ModerationReason,
        moderator_id: Optional[uuid.UUID] = None,
        notes: Optional[str] = None,
        duration_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Apply a moderation action to content
        
        Args:
            content_type: Type of content (video, comment, user)
            content_id: ID of the content
            action: Moderation action to apply
            reason: Reason for the action
            moderator_id: ID of moderator (None for automated)
            notes: Additional notes
            duration_hours: Duration for temporary actions
            
        Returns:
            Action result
        """
        async with self.get_db_session() as db:
            # Create moderation record
            moderation_record = ModerationRecord(
                id=uuid.uuid4(),
                content_type=content_type,
                content_id=content_id,
                action=action.value,
                reason=reason.value,
                moderator_id=moderator_id,
                notes=notes,
                duration_hours=duration_hours,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=duration_hours) if duration_hours else None
            )
            
            db.add(moderation_record)
            
            # Apply the action to the content
            success = await self._execute_moderation_action(
                content_type, content_id, action, db
            )
            
            if success:
                await db.commit()
                
                # Log the moderation event
                await self._log_moderation_event(
                    "moderation_action_applied",
                    content_id,
                    moderator_id,
                    {
                        "content_type": content_type,
                        "action": action.value,
                        "reason": reason.value,
                        "automated": moderator_id is None
                    }
                )
                
                # Notify content creator if applicable
                await self._notify_content_creator(content_type, content_id, action, reason)
                
                return {
                    "success": True,
                    "moderation_id": str(moderation_record.id),
                    "message": f"Moderation action '{action.value}' applied successfully"
                }
            else:
                await db.rollback()
                return {
                    "success": False,
                    "error": "action_failed",
                    "message": "Failed to apply moderation action"
                }
    
    async def get_moderation_queue(
        self,
        moderator_id: uuid.UUID,
        content_type: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get pending moderation items for review
        
        Args:
            moderator_id: ID of the moderator
            content_type: Filter by content type
            priority: Filter by priority level
            limit: Maximum items to return
            
        Returns:
            List of pending moderation items
        """
        async with self.get_db_session() as db:
            # Get pending reports
            stmt = select(ContentReport).where(
                ContentReport.status == "pending"
            )
            
            if content_type:
                stmt = stmt.where(ContentReport.content_type == content_type)
            
            # Order by priority and creation date
            stmt = stmt.order_by(
                ContentReport.created_at.desc()
            ).limit(limit)
            
            result = await db.execute(stmt)
            reports = result.scalars().all()
            
            moderation_items = []
            for report in reports:
                # Get content details
                content_details = await self._get_content_details(
                    report.content_type, report.content_id
                )
                
                # Get scan results if available
                scan_results = await self._get_scan_results(report.content_id)
                
                moderation_items.append({
                    "report_id": str(report.id),
                    "content_type": report.content_type,
                    "content_id": str(report.content_id),
                    "content_details": content_details,
                    "reason": report.reason,
                    "description": report.description,
                    "reporter_id": str(report.reporter_id),
                    "created_at": report.created_at.isoformat(),
                    "scan_results": scan_results,
                    "priority": self._calculate_priority(report, scan_results)
                })
            
            # Sort by priority
            moderation_items.sort(key=lambda x: x["priority"], reverse=True)
            
            return moderation_items
    
    async def resolve_moderation_report(
        self,
        report_id: uuid.UUID,
        moderator_id: uuid.UUID,
        action: ModerationAction,
        reason: Optional[ModerationReason] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resolve a moderation report
        
        Args:
            report_id: ID of the report to resolve
            moderator_id: ID of the moderator
            action: Action taken
            reason: Reason for the action
            notes: Additional notes
            
        Returns:
            Resolution result
        """
        async with self.get_db_session() as db:
            # Get the report
            stmt = select(ContentReport).where(ContentReport.id == report_id)
            result = await db.execute(stmt)
            report = result.scalar_one_or_none()
            
            if not report:
                return {
                    "success": False,
                    "error": "report_not_found",
                    "message": "Report not found"
                }
            
            if report.status != "pending":
                return {
                    "success": False,
                    "error": "report_already_resolved",
                    "message": "Report has already been resolved"
                }
            
            # Apply moderation action if needed
            if action != ModerationAction.APPROVED:
                action_result = await self.apply_moderation_action(
                    content_type=report.content_type,
                    content_id=report.content_id,
                    action=action,
                    reason=reason or ModerationReason.OTHER,
                    moderator_id=moderator_id,
                    notes=notes
                )
                
                if not action_result["success"]:
                    return action_result
            
            # Update report status
            report.status = "resolved"
            report.resolved_by = moderator_id
            report.resolved_at = datetime.utcnow()
            report.resolution_action = action.value
            report.resolution_notes = notes
            
            await db.commit()
            
            return {
                "success": True,
                "message": "Report resolved successfully"
            }
    
    async def get_moderation_history(
        self,
        content_id: uuid.UUID,
        content_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get moderation history for content
        
        Args:
            content_id: ID of the content
            content_type: Type of content
            
        Returns:
            List of moderation actions
        """
        async with self.get_db_session() as db:
            stmt = select(ModerationRecord).where(
                ModerationRecord.content_id == content_id
            )
            
            if content_type:
                stmt = stmt.where(ModerationRecord.content_type == content_type)
            
            stmt = stmt.order_by(ModerationRecord.created_at.desc())
            
            result = await db.execute(stmt)
            records = result.scalars().all()
            
            history = []
            for record in records:
                history.append({
                    "id": str(record.id),
                    "action": record.action,
                    "reason": record.reason,
                    "moderator_id": str(record.moderator_id) if record.moderator_id else None,
                    "notes": record.notes,
                    "created_at": record.created_at.isoformat(),
                    "expires_at": record.expires_at.isoformat() if record.expires_at else None,
                    "automated": record.moderator_id is None
                })
            
            return history
    
    async def _scan_metadata(self, video: Video) -> Dict[str, Any]:
        """Scan video metadata for inappropriate content"""
        flags = []
        risk_level = "low"
        
        # Scan title
        title_scan = self._scan_text_content(video.title)
        if title_scan["flags"]:
            flags.extend([f"title_{flag}" for flag in title_scan["flags"]])
            risk_level = max(risk_level, title_scan["risk_level"], key=self._risk_priority)
        
        # Scan description
        if video.description:
            desc_scan = self._scan_text_content(video.description)
            if desc_scan["flags"]:
                flags.extend([f"description_{flag}" for flag in desc_scan["flags"]])
                risk_level = max(risk_level, desc_scan["risk_level"], key=self._risk_priority)
        
        # Scan tags
        if video.tags:
            for tag in video.tags:
                tag_scan = self._scan_text_content(tag)
                if tag_scan["flags"]:
                    flags.extend([f"tag_{flag}" for flag in tag_scan["flags"]])
                    risk_level = max(risk_level, tag_scan["risk_level"], key=self._risk_priority)
        
        return {
            "risk_level": risk_level,
            "flags": flags,
            "scan_details": {
                "title_clean": not title_scan["flags"],
                "description_clean": not desc_scan["flags"] if video.description else True,
                "tags_clean": not any(self._scan_text_content(tag)["flags"] for tag in (video.tags or []))
            }
        }
    
    async def _scan_visual_content(self, video: Video) -> Dict[str, Any]:
        """Scan video visual content (placeholder for AI integration)"""
        # This would integrate with AI services like AWS Rekognition, Google Vision, etc.
        # For now, return a placeholder result
        return {
            "risk_level": "low",
            "flags": [],
            "scan_details": {
                "explicit_content": False,
                "violence": False,
                "weapons": False,
                "faces_detected": 0,
                "text_detected": False
            }
        }
    
    async def _scan_audio_content(self, video: Video) -> Dict[str, Any]:
        """Scan video audio content (placeholder for AI integration)"""
        # This would integrate with speech-to-text and audio analysis services
        # For now, return a placeholder result
        return {
            "risk_level": "low",
            "flags": [],
            "scan_details": {
                "speech_detected": False,
                "profanity_detected": False,
                "music_detected": False,
                "copyright_match": False
            }
        }
    
    def _scan_text_content(self, text: str) -> Dict[str, Any]:
        """Scan text content for inappropriate material"""
        if not text:
            return {"risk_level": "low", "flags": []}
        
        text_lower = text.lower()
        flags = []
        risk_level = "low"
        
        # Check for profanity
        for pattern in self.profanity_patterns:
            if re.search(pattern, text_lower):
                flags.append("profanity")
                risk_level = "medium"
                break
        
        # Check for spam patterns
        for pattern in self.spam_patterns:
            if re.search(pattern, text_lower):
                flags.append("spam")
                risk_level = "medium"
                break
        
        # Check for hate speech indicators
        hate_indicators = [
            r'\b(hate|kill|die|death)\s+(all|every)\s+\w+',
            r'\b(nazi|hitler|genocide)\b',
            r'\b(terrorist|terrorism)\b'
        ]
        
        for pattern in hate_indicators:
            if re.search(pattern, text_lower):
                flags.append("hate_speech")
                risk_level = "high"
                break
        
        # Check for personal information
        personal_info_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b',  # Credit card
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'  # Email
        ]
        
        for pattern in personal_info_patterns:
            if re.search(pattern, text):
                flags.append("personal_info")
                risk_level = "medium"
                break
        
        # Check for excessive caps (shouting)
        if len(text) > 20 and sum(1 for c in text if c.isupper()) / len(text) > 0.7:
            flags.append("excessive_caps")
        
        # Check for repeated characters (spam indicator)
        if re.search(r'(.)\1{4,}', text):
            flags.append("repeated_chars")
        
        return {
            "risk_level": risk_level,
            "flags": flags
        }
    
    def _load_profanity_patterns(self) -> List[str]:
        """Load profanity detection patterns"""
        # In production, this would load from a comprehensive database
        return [
            r'\b(fuck|shit|damn|hell|bitch|asshole)\b',
            r'\b(stupid|idiot|moron|retard)\b',
        ]
    
    def _load_spam_patterns(self) -> List[str]:
        """Load spam detection patterns"""
        return [
            r'(click here|buy now|limited time|act now)',
            r'(free money|make money|earn \$\d+)',
            r'(viagra|cialis|pharmacy)',
            r'(www\.|http://|https://)',
        ]
    
    def _risk_priority(self, risk_level: str) -> int:
        """Convert risk level to priority number for comparison"""
        priorities = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return priorities.get(risk_level, 1)
    
    def _get_recommended_action(self, risk_level: str) -> ModerationAction:
        """Get recommended moderation action based on risk level"""
        if risk_level == "critical":
            return ModerationAction.REMOVED
        elif risk_level == "high":
            return ModerationAction.HIDDEN
        elif risk_level == "medium":
            return ModerationAction.FLAGGED
        else:
            return ModerationAction.APPROVED
    
    async def _store_scan_results(
        self, 
        content_id: uuid.UUID, 
        results: Dict[str, Any],
        content_type: str = "video"
    ) -> None:
        """Store content scan results"""
        await self._log_moderation_event(
            "content_scanned",
            content_id,
            None,
            {
                "content_type": content_type,
                "scan_results": results
            }
        )
    
    async def _log_moderation_event(
        self,
        event_type: str,
        content_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        data: Dict[str, Any]
    ) -> None:
        """Log moderation events for audit trail"""
        async with self.get_db_session() as db:
            event = AnalyticsEvent(
                event_type=f"moderation_{event_type}",
                user_id=user_id,
                content_id=content_id,
                timestamp=datetime.utcnow(),
                data=data
            )
            
            db.add(event)
            await db.commit()


# Additional models needed for content moderation
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from ..models import Base

class ContentReport(Base):
    """Model for user-submitted content reports"""
    __tablename__ = "content_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    content_type = Column(String(50), nullable=False)  # video, comment, user, channel
    content_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    reason = Column(String(100), nullable=False)
    description = Column(Text)
    evidence_urls = Column(ARRAY(String), default=lambda: [])
    
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, resolved, dismissed
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_action = Column(String(50), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    reporter = relationship("User", foreign_keys=[reporter_id])
    resolver = relationship("User", foreign_keys=[resolved_by])


class ModerationRecord(Base):
    """Model for moderation actions taken on content"""
    __tablename__ = "moderation_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_type = Column(String(50), nullable=False)
    content_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    action = Column(String(50), nullable=False)  # approved, flagged, hidden, removed, etc.
    reason = Column(String(100), nullable=False)
    moderator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # None for automated
    
    notes = Column(Text)
    duration_hours = Column(Integer, nullable=True)  # For temporary actions
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    moderator = relationship("User")