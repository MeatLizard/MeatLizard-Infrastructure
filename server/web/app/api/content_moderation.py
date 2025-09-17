"""
Content Moderation API Endpoints

Provides REST API for content moderation, reporting, and safety features.
"""
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..dependencies import get_current_user, get_db_session
from ..services.content_moderation_service import (
    ContentModerationService, 
    ModerationAction, 
    ModerationReason, 
    ReportType
)
from ..models import User


router = APIRouter(prefix="/api/moderation", tags=["content-moderation"])


# Request/Response Models
class ContentScanRequest(BaseModel):
    video_id: uuid.UUID
    scan_metadata: bool = True
    scan_visual: bool = False
    scan_audio: bool = False


class ContentReportRequest(BaseModel):
    content_type: ReportType
    content_id: uuid.UUID
    reason: ModerationReason
    description: Optional[str] = None
    evidence_urls: Optional[List[str]] = None


class ModerationActionRequest(BaseModel):
    content_type: str = Field(..., regex="^(video|comment|user|channel)$")
    content_id: uuid.UUID
    action: ModerationAction
    reason: ModerationReason
    notes: Optional[str] = None
    duration_hours: Optional[int] = Field(None, ge=1, le=8760)  # Max 1 year


class ResolveReportRequest(BaseModel):
    action: ModerationAction
    reason: Optional[ModerationReason] = None
    notes: Optional[str] = None


@router.post("/scan/video")
async def scan_video_content(
    request: ContentScanRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Scan video content for inappropriate material
    Requires admin privileges or video ownership
    """
    service = ContentModerationService()
    
    # TODO: Add authorization check (admin or video owner)
    
    result = await service.scan_video_content(
        video_id=request.video_id,
        scan_metadata=request.scan_metadata,
        scan_visual=request.scan_visual,
        scan_audio=request.scan_audio
    )
    
    if not result.get("success", True):
        raise HTTPException(status_code=404, detail=result.get("message", "Scan failed"))
    
    return result


@router.post("/scan/comment/{comment_id}")
async def scan_comment_content(
    comment_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Scan comment content for inappropriate material
    Requires admin privileges
    """
    service = ContentModerationService()
    
    # TODO: Add admin authorization check
    
    result = await service.scan_comment_content(comment_id=comment_id)
    
    if not result.get("success", True):
        raise HTTPException(status_code=404, detail=result.get("message", "Scan failed"))
    
    return result


@router.post("/report")
async def submit_content_report(
    request: ContentReportRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Submit a report for inappropriate content
    """
    service = ContentModerationService()
    
    result = await service.submit_content_report(
        reporter_id=current_user.id,
        content_type=request.content_type,
        content_id=request.content_id,
        reason=request.reason,
        description=request.description,
        evidence_urls=request.evidence_urls
    )
    
    if not result["success"]:
        if result["error"] == "already_reported":
            raise HTTPException(status_code=409, detail=result["message"])
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.post("/action")
async def apply_moderation_action(
    request: ModerationActionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Apply a moderation action to content
    Requires moderator privileges
    """
    service = ContentModerationService()
    
    # TODO: Add moderator authorization check
    
    result = await service.apply_moderation_action(
        content_type=request.content_type,
        content_id=request.content_id,
        action=request.action,
        reason=request.reason,
        moderator_id=current_user.id,
        notes=request.notes,
        duration_hours=request.duration_hours
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("message", "Action failed"))
    
    return result


@router.get("/queue")
async def get_moderation_queue(
    current_user: User = Depends(get_current_user),
    content_type: Optional[str] = Query(None, regex="^(video|comment|user|channel)$"),
    priority: Optional[str] = Query(None, regex="^(low|medium|high|critical)$"),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get pending moderation items for review
    Requires moderator privileges
    """
    service = ContentModerationService()
    
    # TODO: Add moderator authorization check
    
    items = await service.get_moderation_queue(
        moderator_id=current_user.id,
        content_type=content_type,
        priority=priority,
        limit=limit
    )
    
    return {
        "items": items,
        "total_count": len(items)
    }


@router.post("/reports/{report_id}/resolve")
async def resolve_moderation_report(
    report_id: uuid.UUID,
    request: ResolveReportRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Resolve a moderation report
    Requires moderator privileges
    """
    service = ContentModerationService()
    
    # TODO: Add moderator authorization check
    
    result = await service.resolve_moderation_report(
        report_id=report_id,
        moderator_id=current_user.id,
        action=request.action,
        reason=request.reason,
        notes=request.notes
    )
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("message", "Resolution failed"))
    
    return result


@router.get("/history/{content_id}")
async def get_moderation_history(
    content_id: uuid.UUID,
    content_type: Optional[str] = Query(None, regex="^(video|comment|user|channel)$"),
    current_user: User = Depends(get_current_user)
):
    """
    Get moderation history for content
    Requires moderator privileges or content ownership
    """
    service = ContentModerationService()
    
    # TODO: Add authorization check (moderator or content owner)
    
    history = await service.get_moderation_history(
        content_id=content_id,
        content_type=content_type
    )
    
    return {
        "content_id": str(content_id),
        "history": history,
        "total_count": len(history)
    }


@router.get("/reasons")
async def get_moderation_reasons():
    """
    Get available moderation reasons
    """
    return {
        "reasons": [
            {
                "value": "inappropriate_content",
                "label": "Inappropriate Content",
                "description": "Content that violates community guidelines"
            },
            {
                "value": "spam",
                "label": "Spam",
                "description": "Unwanted or repetitive content"
            },
            {
                "value": "harassment",
                "label": "Harassment",
                "description": "Content that harasses or bullies others"
            },
            {
                "value": "copyright_violation",
                "label": "Copyright Violation",
                "description": "Content that infringes on copyright"
            },
            {
                "value": "violence",
                "label": "Violence",
                "description": "Content depicting violence or harm"
            },
            {
                "value": "hate_speech",
                "label": "Hate Speech",
                "description": "Content promoting hatred or discrimination"
            },
            {
                "value": "adult_content",
                "label": "Adult Content",
                "description": "Sexually explicit or adult content"
            },
            {
                "value": "misleading_info",
                "label": "Misleading Information",
                "description": "False or misleading information"
            },
            {
                "value": "privacy_violation",
                "label": "Privacy Violation",
                "description": "Content that violates privacy"
            },
            {
                "value": "other",
                "label": "Other",
                "description": "Other policy violations"
            }
        ]
    }


@router.get("/actions")
async def get_moderation_actions():
    """
    Get available moderation actions
    """
    return {
        "actions": [
            {
                "value": "approved",
                "label": "Approve",
                "description": "Content is acceptable"
            },
            {
                "value": "flagged",
                "label": "Flag for Review",
                "description": "Mark content for further review"
            },
            {
                "value": "hidden",
                "label": "Hide",
                "description": "Hide content from public view"
            },
            {
                "value": "removed",
                "label": "Remove",
                "description": "Permanently remove content"
            },
            {
                "value": "restricted",
                "label": "Restrict",
                "description": "Restrict content access"
            },
            {
                "value": "banned",
                "label": "Ban User",
                "description": "Ban the user account"
            }
        ]
    }


@router.get("/stats")
async def get_moderation_stats(
    current_user: User = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365)
):
    """
    Get moderation statistics
    Requires admin privileges
    """
    # TODO: Add admin authorization check
    
    # This would query the database for moderation statistics
    # For now, return placeholder data
    return {
        "period_days": days,
        "total_reports": 0,
        "pending_reports": 0,
        "resolved_reports": 0,
        "auto_moderated": 0,
        "manual_moderated": 0,
        "content_removed": 0,
        "users_banned": 0,
        "top_reasons": []
    }


@router.post("/bulk-action")
async def apply_bulk_moderation_action(
    content_ids: List[uuid.UUID],
    action: ModerationAction,
    reason: ModerationReason,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Apply moderation action to multiple content items
    Requires admin privileges
    """
    service = ContentModerationService()
    
    # TODO: Add admin authorization check
    
    results = []
    for content_id in content_ids:
        try:
            result = await service.apply_moderation_action(
                content_type="video",  # Assuming video for bulk actions
                content_id=content_id,
                action=action,
                reason=reason,
                moderator_id=current_user.id,
                notes=notes
            )
            results.append({
                "content_id": str(content_id),
                "success": result["success"],
                "message": result.get("message", "")
            })
        except Exception as e:
            results.append({
                "content_id": str(content_id),
                "success": False,
                "message": str(e)
            })
    
    successful = sum(1 for r in results if r["success"])
    
    return {
        "total_processed": len(content_ids),
        "successful": successful,
        "failed": len(content_ids) - successful,
        "results": results
    }