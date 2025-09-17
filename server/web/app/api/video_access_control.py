"""
Video Access Control API Endpoints

Provides REST API for managing video visibility and permissions.
"""
import uuid
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..dependencies import get_current_user, get_db_session
from ..services.video_access_control_service import VideoAccessControlService
from ..models import VideoVisibility, User


router = APIRouter(prefix="/api/videos", tags=["video-access-control"])


# Request/Response Models
class VideoAccessRequest(BaseModel):
    video_id: uuid.UUID
    ip_address: Optional[str] = None


class VideoAccessResponse(BaseModel):
    has_access: bool
    reason: str
    message: str


class GrantPermissionRequest(BaseModel):
    video_id: uuid.UUID
    user_id: uuid.UUID
    permission_type: str = Field(default="view", regex="^(view|edit|admin)$")
    expires_at: Optional[datetime] = None


class RevokePermissionRequest(BaseModel):
    video_id: uuid.UUID
    user_id: uuid.UUID


class UpdateVisibilityRequest(BaseModel):
    video_id: uuid.UUID
    visibility: VideoVisibility


class VideoPermissionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str
    permission_type: str
    granted_by: uuid.UUID
    granted_by_name: str
    created_at: str
    expires_at: Optional[str] = None


class VideoPermissionsListResponse(BaseModel):
    success: bool
    permissions: List[VideoPermissionResponse]
    total_count: int


@router.post("/check-access", response_model=VideoAccessResponse)
async def check_video_access(
    request: VideoAccessRequest,
    current_user: Optional[User] = Depends(get_current_user),
    http_request: Request = None
):
    """
    Check if the current user has access to view a specific video
    """
    service = VideoAccessControlService()
    
    # Get IP address from request if not provided
    ip_address = request.ip_address
    if not ip_address and http_request:
        ip_address = http_request.client.host
    
    user_id = current_user.id if current_user else None
    
    result = await service.check_video_access(
        video_id=request.video_id,
        user_id=user_id,
        ip_address=ip_address
    )
    
    return VideoAccessResponse(**result)


@router.post("/grant-permission")
async def grant_video_permission(
    request: GrantPermissionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Grant explicit permission to a user for a video
    Requires video creator or admin privileges
    """
    service = VideoAccessControlService()
    
    result = await service.grant_video_permission(
        video_id=request.video_id,
        user_id=request.user_id,
        granted_by=current_user.id,
        permission_type=request.permission_type,
        expires_at=request.expires_at
    )
    
    if not result["success"]:
        raise HTTPException(status_code=403, detail=result["message"])
    
    return result


@router.post("/revoke-permission")
async def revoke_video_permission(
    request: RevokePermissionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Revoke explicit permission from a user for a video
    Requires video creator or admin privileges
    """
    service = VideoAccessControlService()
    
    result = await service.revoke_video_permission(
        video_id=request.video_id,
        user_id=request.user_id,
        revoked_by=current_user.id
    )
    
    if not result["success"]:
        raise HTTPException(status_code=403, detail=result["message"])
    
    return result


@router.post("/update-visibility")
async def update_video_visibility(
    request: UpdateVisibilityRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Update video visibility setting
    Requires video creator or admin privileges
    """
    service = VideoAccessControlService()
    
    result = await service.update_video_visibility(
        video_id=request.video_id,
        new_visibility=request.visibility,
        updated_by=current_user.id
    )
    
    if not result["success"]:
        raise HTTPException(status_code=403, detail=result["message"])
    
    return result


@router.get("/permissions/{video_id}", response_model=VideoPermissionsListResponse)
async def list_video_permissions(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """
    List all permissions for a video
    Requires video creator or admin privileges
    """
    service = VideoAccessControlService()
    
    result = await service.list_video_permissions(
        video_id=video_id,
        requested_by=current_user.id
    )
    
    if not result["success"]:
        raise HTTPException(status_code=403, detail=result["message"])
    
    # Convert permissions to response models
    permissions = []
    for perm in result["permissions"]:
        permissions.append(VideoPermissionResponse(**perm))
    
    return VideoPermissionsListResponse(
        success=True,
        permissions=permissions,
        total_count=result["total_count"]
    )


@router.get("/visibility-options")
async def get_visibility_options():
    """
    Get available video visibility options
    """
    return {
        "options": [
            {
                "value": "public",
                "label": "Public",
                "description": "Anyone can view this video"
            },
            {
                "value": "unlisted", 
                "label": "Unlisted",
                "description": "Only people with the link can view this video"
            },
            {
                "value": "private",
                "label": "Private", 
                "description": "Only you and people you choose can view this video"
            }
        ]
    }


@router.get("/permission-types")
async def get_permission_types():
    """
    Get available permission types
    """
    return {
        "types": [
            {
                "value": "view",
                "label": "View",
                "description": "Can view the video"
            },
            {
                "value": "edit",
                "label": "Edit",
                "description": "Can view and edit video metadata"
            },
            {
                "value": "admin",
                "label": "Admin",
                "description": "Full control over the video"
            }
        ]
    }