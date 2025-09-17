"""
Channel management API endpoints.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..services.channel_service import ChannelService
from ..models import VideoVisibility
from ..dependencies import get_current_user, get_db


router = APIRouter(prefix="/api/channels", tags=["channels"])


# Request/Response Models
class ChannelCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=5000)
    slug: Optional[str] = Field(None, min_length=1, max_length=100)
    visibility: VideoVisibility = VideoVisibility.public
    category: Optional[str] = Field(None, max_length=50)


class ChannelUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    visibility: Optional[VideoVisibility] = None
    category: Optional[str] = Field(None, max_length=50)
    banner_s3_key: Optional[str] = None
    avatar_s3_key: Optional[str] = None


class ChannelResponse(BaseModel):
    id: uuid.UUID
    creator_id: uuid.UUID
    name: str
    description: Optional[str]
    slug: str
    visibility: VideoVisibility
    category: Optional[str]
    banner_s3_key: Optional[str]
    avatar_s3_key: Optional[str]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class ChannelStatsResponse(BaseModel):
    video_count: int
    playlist_count: int
    total_views: int


# Endpoints
@router.post("/", response_model=ChannelResponse)
async def create_channel(
    request: ChannelCreateRequest,
    current_user = Depends(get_current_user),
    channel_service: ChannelService = Depends()
):
    """Create a new channel."""
    try:
        channel = await channel_service.create_channel(
            creator_id=current_user.id,
            name=request.name,
            description=request.description,
            slug=request.slug,
            visibility=request.visibility,
            category=request.category
        )
        return ChannelResponse.from_orm(channel)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: uuid.UUID,
    channel_service: ChannelService = Depends()
):
    """Get channel by ID."""
    channel = await channel_service.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return ChannelResponse.from_orm(channel)


@router.get("/slug/{slug}", response_model=ChannelResponse)
async def get_channel_by_slug(
    slug: str,
    channel_service: ChannelService = Depends()
):
    """Get channel by slug."""
    channel = await channel_service.get_channel_by_slug(slug)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return ChannelResponse.from_orm(channel)


@router.get("/", response_model=List[ChannelResponse])
async def list_user_channels(
    current_user = Depends(get_current_user),
    include_private: bool = Query(False),
    channel_service: ChannelService = Depends()
):
    """List current user's channels."""
    channels = await channel_service.get_user_channels(
        user_id=current_user.id,
        include_private=include_private
    )
    return [ChannelResponse.from_orm(channel) for channel in channels]


@router.put("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: uuid.UUID,
    request: ChannelUpdateRequest,
    current_user = Depends(get_current_user),
    channel_service: ChannelService = Depends()
):
    """Update channel details."""
    updates = request.dict(exclude_unset=True)
    channel = await channel_service.update_channel(
        channel_id=channel_id,
        user_id=current_user.id,
        **updates
    )
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found or not owned by user")
    
    return ChannelResponse.from_orm(channel)


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: uuid.UUID,
    current_user = Depends(get_current_user),
    channel_service: ChannelService = Depends()
):
    """Delete a channel."""
    success = await channel_service.delete_channel(
        channel_id=channel_id,
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Channel not found or not owned by user")
    
    return {"message": "Channel deleted successfully"}


@router.get("/{channel_id}/videos")
async def get_channel_videos(
    channel_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_user, use_cache=False),
    channel_service: ChannelService = Depends()
):
    """Get videos in a channel."""
    videos = await channel_service.get_channel_videos(
        channel_id=channel_id,
        viewer_user_id=current_user.id if current_user else None,
        limit=limit,
        offset=offset
    )
    
    # Convert to response format (would need VideoResponse model)
    return {"videos": videos, "total": len(videos)}


@router.get("/{channel_id}/playlists")
async def get_channel_playlists(
    channel_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_user, use_cache=False),
    channel_service: ChannelService = Depends()
):
    """Get playlists in a channel."""
    playlists = await channel_service.get_channel_playlists(
        channel_id=channel_id,
        viewer_user_id=current_user.id if current_user else None,
        limit=limit,
        offset=offset
    )
    
    # Convert to response format (would need PlaylistResponse model)
    return {"playlists": playlists, "total": len(playlists)}


@router.get("/{channel_id}/stats", response_model=ChannelStatsResponse)
async def get_channel_stats(
    channel_id: uuid.UUID,
    channel_service: ChannelService = Depends()
):
    """Get channel statistics."""
    stats = await channel_service.get_channel_stats(channel_id)
    return ChannelStatsResponse(**stats)


@router.get("/search/", response_model=List[ChannelResponse])
async def search_channels(
    q: str = Query(..., min_length=1),
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    channel_service: ChannelService = Depends()
):
    """Search channels."""
    channels = await channel_service.search_channels(
        query=q,
        category=category,
        limit=limit,
        offset=offset
    )
    return [ChannelResponse.from_orm(channel) for channel in channels]