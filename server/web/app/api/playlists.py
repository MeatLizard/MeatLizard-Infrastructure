"""
Playlist management API endpoints.
"""
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..services.playlist_service import PlaylistService
from ..models import VideoVisibility
from ..dependencies import get_current_user, get_db


router = APIRouter(prefix="/api/playlists", tags=["playlists"])


# Request/Response Models
class PlaylistCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=5000)
    channel_id: Optional[uuid.UUID] = None
    visibility: VideoVisibility = VideoVisibility.public
    auto_advance: bool = True
    shuffle_enabled: bool = False


class PlaylistUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    visibility: Optional[VideoVisibility] = None
    auto_advance: Optional[bool] = None
    shuffle_enabled: Optional[bool] = None
    thumbnail_s3_key: Optional[str] = None
    channel_id: Optional[uuid.UUID] = None


class AddVideoRequest(BaseModel):
    video_id: uuid.UUID
    position: Optional[int] = None


class ReorderRequest(BaseModel):
    video_positions: List[Dict[str, Any]]


class PlaylistResponse(BaseModel):
    id: uuid.UUID
    creator_id: uuid.UUID
    channel_id: Optional[uuid.UUID]
    name: str
    description: Optional[str]
    visibility: VideoVisibility
    auto_advance: bool
    shuffle_enabled: bool
    thumbnail_s3_key: Optional[str]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class PlaylistItemResponse(BaseModel):
    id: uuid.UUID
    playlist_id: uuid.UUID
    video_id: uuid.UUID
    position: int
    added_at: str
    
    class Config:
        from_attributes = True


class PlaylistStatsResponse(BaseModel):
    video_count: int
    total_duration_seconds: int


# Endpoints
@router.post("/", response_model=PlaylistResponse)
async def create_playlist(
    request: PlaylistCreateRequest,
    current_user = Depends(get_current_user),
    playlist_service: PlaylistService = Depends()
):
    """Create a new playlist."""
    try:
        playlist = await playlist_service.create_playlist(
            creator_id=current_user.id,
            name=request.name,
            description=request.description,
            channel_id=request.channel_id,
            visibility=request.visibility,
            auto_advance=request.auto_advance,
            shuffle_enabled=request.shuffle_enabled
        )
        return PlaylistResponse.from_orm(playlist)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(
    playlist_id: uuid.UUID,
    playlist_service: PlaylistService = Depends()
):
    """Get playlist by ID."""
    playlist = await playlist_service.get_playlist_by_id(playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    return PlaylistResponse.from_orm(playlist)


@router.get("/", response_model=List[PlaylistResponse])
async def list_user_playlists(
    current_user = Depends(get_current_user),
    include_private: bool = Query(False),
    channel_id: Optional[uuid.UUID] = Query(None),
    playlist_service: PlaylistService = Depends()
):
    """List current user's playlists."""
    playlists = await playlist_service.get_user_playlists(
        user_id=current_user.id,
        include_private=include_private,
        channel_id=channel_id
    )
    return [PlaylistResponse.from_orm(playlist) for playlist in playlists]


@router.put("/{playlist_id}", response_model=PlaylistResponse)
async def update_playlist(
    playlist_id: uuid.UUID,
    request: PlaylistUpdateRequest,
    current_user = Depends(get_current_user),
    playlist_service: PlaylistService = Depends()
):
    """Update playlist details."""
    updates = request.dict(exclude_unset=True)
    playlist = await playlist_service.update_playlist(
        playlist_id=playlist_id,
        user_id=current_user.id,
        **updates
    )
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found or not owned by user")
    
    return PlaylistResponse.from_orm(playlist)


@router.delete("/{playlist_id}")
async def delete_playlist(
    playlist_id: uuid.UUID,
    current_user = Depends(get_current_user),
    playlist_service: PlaylistService = Depends()
):
    """Delete a playlist."""
    success = await playlist_service.delete_playlist(
        playlist_id=playlist_id,
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Playlist not found or not owned by user")
    
    return {"message": "Playlist deleted successfully"}


@router.post("/{playlist_id}/videos", response_model=PlaylistItemResponse)
async def add_video_to_playlist(
    playlist_id: uuid.UUID,
    request: AddVideoRequest,
    current_user = Depends(get_current_user),
    playlist_service: PlaylistService = Depends()
):
    """Add a video to a playlist."""
    try:
        item = await playlist_service.add_video_to_playlist(
            playlist_id=playlist_id,
            video_id=request.video_id,
            user_id=current_user.id,
            position=request.position
        )
        
        if not item:
            raise HTTPException(status_code=404, detail="Playlist not found or not owned by user")
        
        return PlaylistItemResponse.from_orm(item)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{playlist_id}/videos/{video_id}")
async def remove_video_from_playlist(
    playlist_id: uuid.UUID,
    video_id: uuid.UUID,
    current_user = Depends(get_current_user),
    playlist_service: PlaylistService = Depends()
):
    """Remove a video from a playlist."""
    success = await playlist_service.remove_video_from_playlist(
        playlist_id=playlist_id,
        video_id=video_id,
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Video not found in playlist or playlist not owned by user")
    
    return {"message": "Video removed from playlist"}


@router.put("/{playlist_id}/reorder")
async def reorder_playlist_items(
    playlist_id: uuid.UUID,
    request: ReorderRequest,
    current_user = Depends(get_current_user),
    playlist_service: PlaylistService = Depends()
):
    """Reorder items in a playlist."""
    success = await playlist_service.reorder_playlist_items(
        playlist_id=playlist_id,
        user_id=current_user.id,
        video_positions=request.video_positions
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Playlist not found or not owned by user")
    
    return {"message": "Playlist reordered successfully"}


@router.get("/{playlist_id}/items", response_model=List[PlaylistItemResponse])
async def get_playlist_items(
    playlist_id: uuid.UUID,
    current_user = Depends(get_current_user, use_cache=False),
    playlist_service: PlaylistService = Depends()
):
    """Get all items in a playlist."""
    items = await playlist_service.get_playlist_items(
        playlist_id=playlist_id,
        viewer_user_id=current_user.id if current_user else None
    )
    return [PlaylistItemResponse.from_orm(item) for item in items]


@router.get("/{playlist_id}/next/{current_video_id}")
async def get_next_video_in_playlist(
    playlist_id: uuid.UUID,
    current_video_id: uuid.UUID,
    shuffle: bool = Query(False),
    playlist_service: PlaylistService = Depends()
):
    """Get the next video in a playlist."""
    next_item = await playlist_service.get_next_video_in_playlist(
        playlist_id=playlist_id,
        current_video_id=current_video_id,
        shuffle=shuffle
    )
    
    if not next_item:
        return {"next_video": None}
    
    return {"next_video": PlaylistItemResponse.from_orm(next_item)}


@router.get("/{playlist_id}/stats", response_model=PlaylistStatsResponse)
async def get_playlist_stats(
    playlist_id: uuid.UUID,
    playlist_service: PlaylistService = Depends()
):
    """Get playlist statistics."""
    stats = await playlist_service.get_playlist_stats(playlist_id)
    return PlaylistStatsResponse(**stats)


@router.get("/search/", response_model=List[PlaylistResponse])
async def search_playlists(
    q: str = Query(..., min_length=1),
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    playlist_service: PlaylistService = Depends()
):
    """Search playlists."""
    playlists = await playlist_service.search_playlists(
        query=q,
        category=category,
        limit=limit,
        offset=offset
    )
    return [PlaylistResponse.from_orm(playlist) for playlist in playlists]