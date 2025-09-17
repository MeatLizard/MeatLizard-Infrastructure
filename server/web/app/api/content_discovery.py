"""
Content discovery and browsing API endpoints.
"""
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..services.content_discovery_service import ContentDiscoveryService, SortOrder
from ..dependencies import get_current_user


router = APIRouter(prefix="/api/discover", tags=["content-discovery"])


# Response Models
class VideoSummaryResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str]
    duration_seconds: int
    thumbnail_s3_key: Optional[str]
    creator_id: uuid.UUID
    creator_name: str
    channel_id: Optional[uuid.UUID]
    channel_name: Optional[str]
    category: Optional[str]
    visibility: str
    created_at: str
    view_count: Optional[int] = 0
    like_count: Optional[int] = 0
    
    class Config:
        from_attributes = True


class ChannelSummaryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    slug: str
    category: Optional[str]
    visibility: str
    creator_name: str
    video_count: Optional[int] = 0
    created_at: str
    
    class Config:
        from_attributes = True


class PlaylistSummaryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    visibility: str
    creator_name: str
    channel_name: Optional[str]
    video_count: Optional[int] = 0
    created_at: str
    
    class Config:
        from_attributes = True


class BrowseVideosResponse(BaseModel):
    videos: List[VideoSummaryResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class SearchResponse(BaseModel):
    videos: Optional[Dict[str, Any]] = None
    channels: Optional[Dict[str, Any]] = None
    playlists: Optional[Dict[str, Any]] = None
    query: str


class CategoryResponse(BaseModel):
    name: str
    video_count: int
    channel_count: int


# Endpoints
@router.get("/videos", response_model=BrowseVideosResponse)
async def browse_videos(
    channel_id: Optional[uuid.UUID] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None, alias="q"),
    sort: SortOrder = Query(SortOrder.newest),
    min_duration: Optional[int] = Query(None, ge=0),
    max_duration: Optional[int] = Query(None, ge=0),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user = Depends(get_current_user, use_cache=False),
    discovery_service: ContentDiscoveryService = Depends()
):
    """Browse videos with filtering and sorting."""
    offset = (page - 1) * per_page
    
    videos, total = await discovery_service.browse_videos(
        viewer_user_id=current_user.id if current_user else None,
        channel_id=channel_id,
        category=category,
        search_query=search,
        sort_order=sort,
        min_duration=min_duration,
        max_duration=max_duration,
        date_from=date_from,
        date_to=date_to,
        limit=per_page,
        offset=offset
    )
    
    # Convert to response format
    video_responses = []
    for video in videos:
        video_responses.append(VideoSummaryResponse(
            id=video.id,
            title=video.title,
            description=video.description,
            duration_seconds=video.duration_seconds,
            thumbnail_s3_key=video.thumbnail_s3_key,
            creator_id=video.creator_id,
            creator_name=video.creator.display_label if video.creator else "Unknown",
            channel_id=video.channel_id,
            channel_name=video.channel.name if video.channel else None,
            category=video.category,
            visibility=video.visibility.value,
            created_at=video.created_at.isoformat(),
            view_count=0,  # Would need to be calculated
            like_count=0   # Would need to be calculated
        ))
    
    return BrowseVideosResponse(
        videos=video_responses,
        total=total,
        page=page,
        per_page=per_page,
        has_next=offset + per_page < total,
        has_prev=page > 1
    )


@router.get("/search", response_model=SearchResponse)
async def search_content(
    q: str = Query(..., min_length=1),
    types: List[str] = Query(["videos", "channels", "playlists"]),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user = Depends(get_current_user, use_cache=False),
    discovery_service: ContentDiscoveryService = Depends()
):
    """Search across videos, channels, and playlists."""
    offset = (page - 1) * per_page
    
    results = await discovery_service.search_content(
        search_query=q,
        content_types=types,
        viewer_user_id=current_user.id if current_user else None,
        limit=per_page,
        offset=offset
    )
    
    # Convert results to response format
    response_data = {"query": q}
    
    if "videos" in results:
        video_responses = []
        for video in results["videos"]["items"]:
            video_responses.append(VideoSummaryResponse(
                id=video.id,
                title=video.title,
                description=video.description,
                duration_seconds=video.duration_seconds,
                thumbnail_s3_key=video.thumbnail_s3_key,
                creator_id=video.creator_id,
                creator_name=video.creator.display_label if video.creator else "Unknown",
                channel_id=video.channel_id,
                channel_name=video.channel.name if video.channel else None,
                category=video.category,
                visibility=video.visibility.value,
                created_at=video.created_at.isoformat()
            ))
        
        response_data["videos"] = {
            "items": video_responses,
            "total": results["videos"]["total"]
        }
    
    if "channels" in results:
        channel_responses = []
        for channel in results["channels"]["items"]:
            channel_responses.append(ChannelSummaryResponse(
                id=channel.id,
                name=channel.name,
                description=channel.description,
                slug=channel.slug,
                category=channel.category,
                visibility=channel.visibility.value,
                creator_name=channel.creator.display_label if channel.creator else "Unknown",
                created_at=channel.created_at.isoformat()
            ))
        
        response_data["channels"] = {
            "items": channel_responses,
            "total": results["channels"]["total"]
        }
    
    if "playlists" in results:
        playlist_responses = []
        for playlist in results["playlists"]["items"]:
            playlist_responses.append(PlaylistSummaryResponse(
                id=playlist.id,
                name=playlist.name,
                description=playlist.description,
                visibility=playlist.visibility.value,
                creator_name=playlist.creator.display_label if playlist.creator else "Unknown",
                channel_name=playlist.channel.name if playlist.channel else None,
                created_at=playlist.created_at.isoformat()
            ))
        
        response_data["playlists"] = {
            "items": playlist_responses,
            "total": results["playlists"]["total"]
        }
    
    return SearchResponse(**response_data)


@router.get("/trending", response_model=List[VideoSummaryResponse])
async def get_trending_videos(
    timeframe: str = Query("week", regex="^(day|week|month|all)$"),
    limit: int = Query(20, ge=1, le=100),
    current_user = Depends(get_current_user, use_cache=False),
    discovery_service: ContentDiscoveryService = Depends()
):
    """Get trending videos."""
    videos = await discovery_service.get_trending_videos(
        timeframe=timeframe,
        viewer_user_id=current_user.id if current_user else None,
        limit=limit
    )
    
    return [
        VideoSummaryResponse(
            id=video.id,
            title=video.title,
            description=video.description,
            duration_seconds=video.duration_seconds,
            thumbnail_s3_key=video.thumbnail_s3_key,
            creator_id=video.creator_id,
            creator_name=video.creator.display_label if video.creator else "Unknown",
            channel_id=video.channel_id,
            channel_name=video.channel.name if video.channel else None,
            category=video.category,
            visibility=video.visibility.value,
            created_at=video.created_at.isoformat()
        )
        for video in videos
    ]


@router.get("/popular", response_model=List[VideoSummaryResponse])
async def get_popular_videos(
    timeframe: str = Query("week", regex="^(day|week|month|all)$"),
    limit: int = Query(20, ge=1, le=100),
    current_user = Depends(get_current_user, use_cache=False),
    discovery_service: ContentDiscoveryService = Depends()
):
    """Get popular videos based on likes."""
    videos = await discovery_service.get_popular_videos(
        timeframe=timeframe,
        viewer_user_id=current_user.id if current_user else None,
        limit=limit
    )
    
    return [
        VideoSummaryResponse(
            id=video.id,
            title=video.title,
            description=video.description,
            duration_seconds=video.duration_seconds,
            thumbnail_s3_key=video.thumbnail_s3_key,
            creator_id=video.creator_id,
            creator_name=video.creator.display_label if video.creator else "Unknown",
            channel_id=video.channel_id,
            channel_name=video.channel.name if video.channel else None,
            category=video.category,
            visibility=video.visibility.value,
            created_at=video.created_at.isoformat()
        )
        for video in videos
    ]


@router.get("/recommended", response_model=List[VideoSummaryResponse])
async def get_recommended_videos(
    limit: int = Query(20, ge=1, le=100),
    current_user = Depends(get_current_user),
    discovery_service: ContentDiscoveryService = Depends()
):
    """Get personalized video recommendations."""
    videos = await discovery_service.get_recommended_videos(
        user_id=current_user.id,
        limit=limit
    )
    
    return [
        VideoSummaryResponse(
            id=video.id,
            title=video.title,
            description=video.description,
            duration_seconds=video.duration_seconds,
            thumbnail_s3_key=video.thumbnail_s3_key,
            creator_id=video.creator_id,
            creator_name=video.creator.display_label if video.creator else "Unknown",
            channel_id=video.channel_id,
            channel_name=video.channel.name if video.channel else None,
            category=video.category,
            visibility=video.visibility.value,
            created_at=video.created_at.isoformat()
        )
        for video in videos
    ]


@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(
    discovery_service: ContentDiscoveryService = Depends()
):
    """Get all available categories with counts."""
    categories = await discovery_service.get_categories()
    return [CategoryResponse(**category) for category in categories]


@router.get("/related/{video_id}", response_model=List[VideoSummaryResponse])
async def get_related_videos(
    video_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=20),
    current_user = Depends(get_current_user, use_cache=False),
    discovery_service: ContentDiscoveryService = Depends()
):
    """Get videos related to the specified video."""
    videos = await discovery_service.get_related_videos(
        video_id=video_id,
        viewer_user_id=current_user.id if current_user else None,
        limit=limit
    )
    
    return [
        VideoSummaryResponse(
            id=video.id,
            title=video.title,
            description=video.description,
            duration_seconds=video.duration_seconds,
            thumbnail_s3_key=video.thumbnail_s3_key,
            creator_id=video.creator_id,
            creator_name=video.creator.display_label if video.creator else "Unknown",
            channel_id=video.channel_id,
            channel_name=video.channel.name if video.channel else None,
            category=video.category,
            visibility=video.visibility.value,
            created_at=video.created_at.isoformat()
        )
        for video in videos
    ]


@router.get("/latest", response_model=List[VideoSummaryResponse])
async def get_latest_videos(
    limit: int = Query(20, ge=1, le=100),
    current_user = Depends(get_current_user, use_cache=False),
    discovery_service: ContentDiscoveryService = Depends()
):
    """Get the latest uploaded videos."""
    videos = await discovery_service.get_latest_videos(
        viewer_user_id=current_user.id if current_user else None,
        limit=limit
    )
    
    return [
        VideoSummaryResponse(
            id=video.id,
            title=video.title,
            description=video.description,
            duration_seconds=video.duration_seconds,
            thumbnail_s3_key=video.thumbnail_s3_key,
            creator_id=video.creator_id,
            creator_name=video.creator.display_label if video.creator else "Unknown",
            channel_id=video.channel_id,
            channel_name=video.channel.name if video.channel else None,
            category=video.category,
            visibility=video.visibility.value,
            created_at=video.created_at.isoformat()
        )
        for video in videos
    ]


@router.get("/creator/{creator_id}", response_model=List[VideoSummaryResponse])
async def get_videos_by_creator(
    creator_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_user, use_cache=False),
    discovery_service: ContentDiscoveryService = Depends()
):
    """Get videos by a specific creator."""
    videos = await discovery_service.get_videos_by_creator(
        creator_id=creator_id,
        viewer_user_id=current_user.id if current_user else None,
        limit=limit,
        offset=offset
    )
    
    return [
        VideoSummaryResponse(
            id=video.id,
            title=video.title,
            description=video.description,
            duration_seconds=video.duration_seconds,
            thumbnail_s3_key=video.thumbnail_s3_key,
            creator_id=video.creator_id,
            creator_name=video.creator.display_label if video.creator else "Unknown",
            channel_id=video.channel_id,
            channel_name=video.channel.name if video.channel else None,
            category=video.category,
            visibility=video.visibility.value,
            created_at=video.created_at.isoformat()
        )
        for video in videos
    ]


@router.get("/sections")
async def get_discovery_sections(
    current_user = Depends(get_current_user, use_cache=False),
    discovery_service: ContentDiscoveryService = Depends()
):
    """Get multiple discovery sections for the home page."""
    sections = await discovery_service.get_discovery_sections(
        viewer_user_id=current_user.id if current_user else None
    )
    
    # Convert each section to response format
    response_sections = {}
    for section_name, videos in sections.items():
        response_sections[section_name] = [
            VideoSummaryResponse(
                id=video.id,
                title=video.title,
                description=video.description,
                duration_seconds=video.duration_seconds,
                thumbnail_s3_key=video.thumbnail_s3_key,
                creator_id=video.creator_id,
                creator_name=video.creator.display_label if video.creator else "Unknown",
                channel_id=video.channel_id,
                channel_name=video.channel.name if video.channel else None,
                category=video.category,
                visibility=video.visibility.value,
                created_at=video.created_at.isoformat()
            )
            for video in videos
        ]
    
    return response_sections


@router.get("/analytics/{video_id}")
async def get_video_analytics(
    video_id: uuid.UUID,
    discovery_service: ContentDiscoveryService = Depends()
):
    """Get analytics data for a video (for discovery algorithms)."""
    analytics = await discovery_service.get_video_analytics_for_discovery(video_id)
    return analytics