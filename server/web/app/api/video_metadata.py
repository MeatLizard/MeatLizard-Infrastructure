"""
Video Metadata API Endpoints

Provides REST API endpoints for video metadata management including:
- Metadata creation and updates
- Tag management and suggestions
- Metadata search and retrieval
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.video_metadata_service import (
    VideoMetadataService,
    VideoMetadataInput,
    VideoMetadataUpdate,
    VideoMetadataResponse,
    TagSuggestion,
    get_video_metadata_service
)
from server.web.app.models import User
from server.web.app.middleware.permissions import get_current_user

router = APIRouter(prefix="/api/video/metadata", tags=["video-metadata"])


# Request/Response Models
class CreateMetadataRequest(BaseModel):
    title: str
    description: Optional[str] = None
    tags: List[str] = []


class UpdateMetadataRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class BulkTagUpdateRequest(BaseModel):
    video_ids: List[str]
    tags_to_add: List[str] = []
    tags_to_remove: List[str] = []


class SearchRequest(BaseModel):
    query: Optional[str] = None
    tags: Optional[List[str]] = None
    creator_id: Optional[str] = None
    limit: int = 50
    offset: int = 0


class TagParseRequest(BaseModel):
    tags_string: str


class TagParseResponse(BaseModel):
    original_string: str
    parsed_tags: List[str]
    invalid_tags: List[str] = []


@router.post("/videos/{video_id}", response_model=VideoMetadataResponse)
async def create_video_metadata(
    video_id: str,
    request: CreateMetadataRequest,
    user: User = Depends(get_current_user),
    service: VideoMetadataService = Depends(get_video_metadata_service)
):
    """
    Create or update metadata for a video during upload.
    
    This endpoint allows content creators to set title, description, and tags
    for their videos during the upload process.
    
    Requirements: 3.1, 3.5
    """
    try:
        # Validate and create metadata
        metadata_input = VideoMetadataInput(
            title=request.title,
            description=request.description,
            tags=request.tags
        )
        
        result = await service.create_metadata(video_id, metadata_input, str(user.id))
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create metadata: {str(e)}")


@router.put("/videos/{video_id}", response_model=VideoMetadataResponse)
async def update_video_metadata(
    video_id: str,
    request: UpdateMetadataRequest,
    user: User = Depends(get_current_user),
    service: VideoMetadataService = Depends(get_video_metadata_service)
):
    """
    Update existing video metadata.
    
    This endpoint allows content creators to modify the title, description,
    and tags of their existing videos.
    
    Requirements: 3.1, 3.5
    """
    try:
        # Validate and update metadata
        metadata_update = VideoMetadataUpdate(
            title=request.title,
            description=request.description,
            tags=request.tags
        )
        
        result = await service.update_metadata(video_id, metadata_update, str(user.id))
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update metadata: {str(e)}")


@router.get("/videos/{video_id}", response_model=VideoMetadataResponse)
async def get_video_metadata(
    video_id: str,
    user: User = Depends(get_current_user),
    service: VideoMetadataService = Depends(get_video_metadata_service)
):
    """
    Get metadata for a specific video.
    
    This endpoint retrieves the title, description, tags, and other metadata
    for a video, respecting visibility permissions.
    
    Requirements: 3.5
    """
    try:
        result = await service.get_metadata(video_id, str(user.id))
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metadata: {str(e)}")


@router.get("/videos/{video_id}/public", response_model=VideoMetadataResponse)
async def get_video_metadata_public(
    video_id: str,
    service: VideoMetadataService = Depends(get_video_metadata_service)
):
    """
    Get metadata for a public video without authentication.
    
    This endpoint allows unauthenticated access to public video metadata
    for sharing and embedding purposes.
    
    Requirements: 3.5
    """
    try:
        result = await service.get_metadata(video_id, None)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metadata: {str(e)}")


@router.get("/users/{user_id}/videos", response_model=List[VideoMetadataResponse])
async def get_user_videos_metadata(
    user_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    service: VideoMetadataService = Depends(get_video_metadata_service)
):
    """
    Get metadata for all videos by a specific user.
    
    This endpoint returns a paginated list of video metadata for videos
    created by the specified user.
    
    Requirements: 3.5
    """
    try:
        # Only allow users to see their own videos or implement proper access control
        if str(current_user.id) != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to view these videos")
        
        result = await service.get_user_videos_metadata(user_id, limit, offset)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user videos: {str(e)}")


@router.post("/search", response_model=List[VideoMetadataResponse])
async def search_videos_by_metadata(
    request: SearchRequest,
    user: User = Depends(get_current_user),
    service: VideoMetadataService = Depends(get_video_metadata_service)
):
    """
    Search videos by title, description, and tags.
    
    This endpoint provides full-text search across video metadata,
    supporting filtering by tags and creator.
    
    Requirements: 3.5
    """
    try:
        result = await service.search_videos_by_metadata(
            query=request.query,
            tags=request.tags,
            creator_id=request.creator_id,
            limit=request.limit,
            offset=request.offset
        )
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/tags/popular", response_model=List[TagSuggestion])
async def get_popular_tags(
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    service: VideoMetadataService = Depends(get_video_metadata_service)
):
    """
    Get popular tags across all videos.
    
    This endpoint returns the most commonly used tags to help users
    discover content and suggest tags for their own videos.
    
    Requirements: 3.1
    """
    try:
        result = await service.get_popular_tags(limit)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get popular tags: {str(e)}")


@router.get("/tags/{tag}/related", response_model=List[str])
async def get_related_tags(
    tag: str,
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    service: VideoMetadataService = Depends(get_video_metadata_service)
):
    """
    Get tags that are commonly used together with the given tag.
    
    This endpoint helps users discover related tags and improve
    their video tagging for better discoverability.
    
    Requirements: 3.1
    """
    try:
        result = await service.get_related_tags(tag, limit)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get related tags: {str(e)}")


@router.post("/tags/parse", response_model=TagParseResponse)
async def parse_tags_from_string(
    request: TagParseRequest,
    user: User = Depends(get_current_user),
    service: VideoMetadataService = Depends(get_video_metadata_service)
):
    """
    Parse and normalize tags from a comma-separated string.
    
    This endpoint helps users input tags in a natural format and
    provides feedback on tag normalization and validation.
    
    Requirements: 3.1
    """
    try:
        parsed_tags = service.parse_tags_from_string(request.tags_string)
        
        # For now, we'll assume all parsed tags are valid
        # In a more sophisticated implementation, you could track invalid tags
        return TagParseResponse(
            original_string=request.tags_string,
            parsed_tags=parsed_tags,
            invalid_tags=[]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse tags: {str(e)}")


@router.post("/tags/bulk-update")
async def bulk_update_video_tags(
    request: BulkTagUpdateRequest,
    user: User = Depends(get_current_user),
    service: VideoMetadataService = Depends(get_video_metadata_service)
):
    """
    Bulk update tags for multiple videos.
    
    This endpoint allows content creators to add or remove tags
    from multiple videos at once for efficient content management.
    
    Requirements: 3.1
    """
    try:
        updated_count = await service.bulk_update_tags(
            video_ids=request.video_ids,
            tags_to_add=request.tags_to_add,
            tags_to_remove=request.tags_to_remove,
            user_id=str(user.id)
        )
        
        return {
            "message": f"Updated tags for {updated_count} videos",
            "updated_count": updated_count,
            "total_requested": len(request.video_ids)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk update failed: {str(e)}")


@router.post("/validate")
async def validate_metadata(
    metadata: Dict[str, Any],
    user: User = Depends(get_current_user),
    service: VideoMetadataService = Depends(get_video_metadata_service)
):
    """
    Validate video metadata without saving.
    
    This endpoint allows users to validate their metadata input
    before submitting, providing immediate feedback on validation errors.
    
    Requirements: 3.1
    """
    try:
        validated_metadata = service.validate_metadata_input(metadata)
        
        return {
            "valid": True,
            "validated_metadata": {
                "title": validated_metadata.title,
                "description": validated_metadata.description,
                "tags": validated_metadata.tags
            },
            "message": "Metadata validation passed"
        }
        
    except HTTPException as e:
        return {
            "valid": False,
            "error": e.detail,
            "message": "Metadata validation failed"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.get("/stats")
async def get_metadata_stats(
    user: User = Depends(get_current_user),
    service: VideoMetadataService = Depends(get_video_metadata_service)
):
    """
    Get statistics about video metadata usage.
    
    This endpoint provides insights into tag usage, content distribution,
    and other metadata statistics for analytics purposes.
    
    Requirements: 3.5
    """
    try:
        # Get user's videos
        user_videos = await service.get_user_videos_metadata(str(user.id), limit=1000)
        
        # Calculate statistics
        total_videos = len(user_videos)
        total_tags = sum(len(video.tags) for video in user_videos)
        unique_tags = len(set(tag for video in user_videos for tag in video.tags))
        
        # Most used tags by this user
        tag_counts = {}
        for video in user_videos:
            for tag in video.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        most_used_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "total_videos": total_videos,
            "total_tags": total_tags,
            "unique_tags": unique_tags,
            "average_tags_per_video": total_tags / total_videos if total_videos > 0 else 0,
            "most_used_tags": [{"tag": tag, "count": count} for tag, count in most_used_tags],
            "videos_with_descriptions": sum(1 for video in user_videos if video.description),
            "description_usage_percent": (sum(1 for video in user_videos if video.description) / total_videos * 100) if total_videos > 0 else 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")