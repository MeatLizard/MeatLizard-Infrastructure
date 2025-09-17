"""
Video Metadata Service

Handles video metadata collection, validation, and management including:
- Title, description, and tags input validation
- Tag parsing and normalization
- Metadata storage and retrieval
"""
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from pydantic import BaseModel, validator

from server.web.app.models import Video, User
from server.web.app.services.base_service import BaseService
from server.web.app.services.video_cache_service import VideoCacheService


class VideoMetadataInput(BaseModel):
    """Input model for video metadata"""
    title: str
    description: Optional[str] = None
    tags: List[str] = []
    
    @validator('title')
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError('Title is required')
        if len(v.strip()) > 100:
            raise ValueError('Title must be 100 characters or less')
        return v.strip()
    
    @validator('description')
    def validate_description(cls, v):
        if v is not None:
            if len(v) > 5000:
                raise ValueError('Description must be 5000 characters or less')
            return v.strip() if v.strip() else None
        return v
    
    @validator('tags')
    def validate_tags(cls, v):
        if len(v) > 20:
            raise ValueError('Maximum 20 tags allowed')
        
        normalized_tags = []
        for tag in v:
            if isinstance(tag, str):
                normalized_tag = cls._normalize_tag(tag)
                if normalized_tag and normalized_tag not in normalized_tags:
                    normalized_tags.append(normalized_tag)
        
        return normalized_tags[:20]  # Ensure max 20 tags
    
    @staticmethod
    def _normalize_tag(tag: str) -> Optional[str]:
        """Normalize a single tag"""
        if not tag or not isinstance(tag, str):
            return None
        
        # Remove extra whitespace and convert to lowercase
        normalized = tag.strip().lower()
        
        # Remove special characters except hyphens and underscores
        normalized = re.sub(r'[^\w\-_]', '', normalized)
        
        # Ensure tag is not empty and within length limits
        if not normalized or len(normalized) < 2 or len(normalized) > 30:
            return None
        
        return normalized


class VideoMetadataUpdate(BaseModel):
    """Model for updating video metadata"""
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    
    @validator('title')
    def validate_title(cls, v):
        if v is not None:
            if not v.strip():
                raise ValueError('Title cannot be empty')
            if len(v.strip()) > 100:
                raise ValueError('Title must be 100 characters or less')
            return v.strip()
        return v
    
    @validator('description')
    def validate_description(cls, v):
        if v is not None:
            if len(v) > 5000:
                raise ValueError('Description must be 5000 characters or less')
            return v.strip() if v.strip() else None
        return v
    
    @validator('tags')
    def validate_tags(cls, v):
        if v is not None:
            return VideoMetadataInput.validate_tags(v)
        return v


class VideoMetadataResponse(BaseModel):
    """Response model for video metadata"""
    video_id: str
    title: str
    description: Optional[str]
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    creator_id: str
    creator_name: str


class TagSuggestion(BaseModel):
    """Model for tag suggestions"""
    tag: str
    usage_count: int
    related_tags: List[str] = []


class VideoMetadataService(BaseService):
    """Service for handling video metadata operations"""
    
    def __init__(self, db: AsyncSession, cache_service: VideoCacheService = None):
        self.db = db
        self.cache_service = cache_service
    
    async def create_metadata(self, video_id: str, metadata: VideoMetadataInput, creator_id: str) -> VideoMetadataResponse:
        """Create metadata for a new video"""
        
        # Get video record
        video = await self.db.get(Video, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Verify ownership
        if str(video.creator_id) != creator_id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this video")
        
        # Update video metadata
        video.title = metadata.title
        video.description = metadata.description
        video.tags = metadata.tags
        video.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(video)
        
        # Invalidate cache if cache service is available
        if self.cache_service:
            await self.cache_service.invalidate_video_metadata(video_id)
        
        # Get creator info
        creator = await self.db.get(User, creator_id)
        
        return VideoMetadataResponse(
            video_id=str(video.id),
            title=video.title,
            description=video.description,
            tags=video.tags or [],
            created_at=video.created_at,
            updated_at=video.updated_at,
            creator_id=str(video.creator_id),
            creator_name=creator.display_label if creator else "Unknown"
        )
    
    async def update_metadata(self, video_id: str, metadata: VideoMetadataUpdate, user_id: str) -> VideoMetadataResponse:
        """Update existing video metadata"""
        
        # Get video record
        video = await self.db.get(Video, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Verify ownership
        if str(video.creator_id) != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this video")
        
        # Update fields that are provided
        if metadata.title is not None:
            video.title = metadata.title
        if metadata.description is not None:
            video.description = metadata.description
        if metadata.tags is not None:
            video.tags = metadata.tags
        
        video.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(video)
        
        # Invalidate cache if cache service is available
        if self.cache_service:
            await self.cache_service.invalidate_video_metadata(video_id)
        
        # Get creator info
        creator = await self.db.get(User, user_id)
        
        return VideoMetadataResponse(
            video_id=str(video.id),
            title=video.title,
            description=video.description,
            tags=video.tags or [],
            created_at=video.created_at,
            updated_at=video.updated_at,
            creator_id=str(video.creator_id),
            creator_name=creator.display_label if creator else "Unknown"
        )
    
    async def get_metadata(self, video_id: str, user_id: Optional[str] = None) -> VideoMetadataResponse:
        """Get video metadata"""
        
        # Try cache first if cache service is available
        if self.cache_service:
            cached_metadata = await self.cache_service.get_video_metadata(video_id)
            if cached_metadata:
                # Check access control for cached data
                if cached_metadata.get('visibility') == 'private' and (not user_id or cached_metadata.get('creator', {}).get('id') != user_id):
                    raise HTTPException(status_code=403, detail="Not authorized to view this video")
                
                return VideoMetadataResponse(
                    video_id=cached_metadata['id'],
                    title=cached_metadata['title'],
                    description=cached_metadata['description'],
                    tags=cached_metadata['tags'],
                    created_at=datetime.fromisoformat(cached_metadata['created_at']),
                    updated_at=datetime.fromisoformat(cached_metadata['updated_at']),
                    creator_id=cached_metadata['creator']['id'],
                    creator_name=cached_metadata['creator']['name']
                )
        
        # Get video record with creator info from database
        stmt = select(Video, User).join(User, Video.creator_id == User.id).where(Video.id == video_id)
        result = await self.db.execute(stmt)
        row = result.first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Video not found")
        
        video, creator = row
        
        # Check if user has access to this video (basic check)
        # More sophisticated access control will be implemented in the access control service
        if video.visibility.value == 'private' and (not user_id or str(video.creator_id) != user_id):
            raise HTTPException(status_code=403, detail="Not authorized to view this video")
        
        response = VideoMetadataResponse(
            video_id=str(video.id),
            title=video.title,
            description=video.description,
            tags=video.tags or [],
            created_at=video.created_at,
            updated_at=video.updated_at,
            creator_id=str(video.creator_id),
            creator_name=creator.display_label
        )
        
        # Cache the metadata if cache service is available
        if self.cache_service:
            metadata_dict = {
                'id': str(video.id),
                'title': video.title,
                'description': video.description,
                'tags': video.tags or [],
                'visibility': video.visibility.value,
                'status': video.status.value,
                'duration_seconds': video.duration_seconds,
                'source_resolution': video.source_resolution,
                'source_framerate': video.source_framerate,
                'file_size': video.file_size,
                'thumbnail_s3_key': video.thumbnail_s3_key,
                'created_at': video.created_at.isoformat(),
                'updated_at': video.updated_at.isoformat(),
                'creator': {
                    'id': str(creator.id),
                    'name': creator.display_label,
                }
            }
            await self.cache_service.set_video_metadata(video_id, metadata_dict)
        
        return response
    
    async def get_user_videos_metadata(self, user_id: str, limit: int = 50, offset: int = 0) -> List[VideoMetadataResponse]:
        """Get metadata for all videos by a user"""
        
        # Get user's videos with creator info
        stmt = (
            select(Video, User)
            .join(User, Video.creator_id == User.id)
            .where(Video.creator_id == user_id)
            .order_by(Video.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        return [
            VideoMetadataResponse(
                video_id=str(video.id),
                title=video.title,
                description=video.description,
                tags=video.tags or [],
                created_at=video.created_at,
                updated_at=video.updated_at,
                creator_id=str(video.creator_id),
                creator_name=creator.display_label
            )
            for video, creator in rows
        ]
    
    async def search_videos_by_metadata(
        self, 
        query: str, 
        tags: Optional[List[str]] = None,
        creator_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[VideoMetadataResponse]:
        """Search videos by title, description, and tags"""
        
        # Build search query
        stmt = select(Video, User).join(User, Video.creator_id == User.id)
        
        # Add text search conditions
        if query:
            search_term = f"%{query.lower()}%"
            stmt = stmt.where(
                (Video.title.ilike(search_term)) |
                (Video.description.ilike(search_term))
            )
        
        # Add tag filter
        if tags:
            # PostgreSQL JSONB contains operator
            for tag in tags:
                stmt = stmt.where(Video.tags.op('@>')([tag]))
        
        # Add creator filter
        if creator_id:
            stmt = stmt.where(Video.creator_id == creator_id)
        
        # Only show public and unlisted videos for search
        stmt = stmt.where(Video.visibility.in_(['public', 'unlisted']))
        
        # Order and limit
        stmt = stmt.order_by(Video.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        return [
            VideoMetadataResponse(
                video_id=str(video.id),
                title=video.title,
                description=video.description,
                tags=video.tags or [],
                created_at=video.created_at,
                updated_at=video.updated_at,
                creator_id=str(video.creator_id),
                creator_name=creator.display_label
            )
            for video, creator in rows
        ]
    
    async def get_popular_tags(self, limit: int = 50) -> List[TagSuggestion]:
        """Get popular tags across all videos"""
        
        # This is a simplified implementation
        # In production, you might want to use a more sophisticated approach
        # with proper tag analytics and caching
        
        stmt = select(Video.tags).where(Video.tags.isnot(None))
        result = await self.db.execute(stmt)
        
        # Count tag occurrences
        tag_counts = {}
        for (tags,) in result:
            if tags:
                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # Sort by usage count and return top tags
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        return [
            TagSuggestion(tag=tag, usage_count=count)
            for tag, count in sorted_tags
        ]
    
    async def get_related_tags(self, tag: str, limit: int = 10) -> List[str]:
        """Get tags that are commonly used together with the given tag"""
        
        # Find videos that contain the given tag
        stmt = select(Video.tags).where(Video.tags.op('@>')([tag]))
        result = await self.db.execute(stmt)
        
        # Count co-occurring tags
        related_tag_counts = {}
        for (tags,) in result:
            if tags:
                for related_tag in tags:
                    if related_tag != tag:
                        related_tag_counts[related_tag] = related_tag_counts.get(related_tag, 0) + 1
        
        # Sort by co-occurrence count and return top related tags
        sorted_related = sorted(related_tag_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        return [tag for tag, count in sorted_related]
    
    def parse_tags_from_string(self, tags_string: str) -> List[str]:
        """Parse tags from a comma-separated string"""
        
        if not tags_string:
            return []
        
        # Split by comma and normalize each tag
        raw_tags = [tag.strip() for tag in tags_string.split(',')]
        normalized_tags = []
        
        for tag in raw_tags:
            normalized = VideoMetadataInput._normalize_tag(tag)
            if normalized and normalized not in normalized_tags:
                normalized_tags.append(normalized)
        
        return normalized_tags[:20]  # Limit to 20 tags
    
    def validate_metadata_input(self, metadata: Dict[str, Any]) -> VideoMetadataInput:
        """Validate and normalize metadata input"""
        
        try:
            return VideoMetadataInput(**metadata)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    async def bulk_update_tags(self, video_ids: List[str], tags_to_add: List[str], tags_to_remove: List[str], user_id: str) -> int:
        """Bulk update tags for multiple videos"""
        
        updated_count = 0
        
        for video_id in video_ids:
            try:
                video = await self.db.get(Video, video_id)
                if not video or str(video.creator_id) != user_id:
                    continue
                
                current_tags = set(video.tags or [])
                
                # Add new tags
                for tag in tags_to_add:
                    normalized_tag = VideoMetadataInput._normalize_tag(tag)
                    if normalized_tag:
                        current_tags.add(normalized_tag)
                
                # Remove tags
                for tag in tags_to_remove:
                    current_tags.discard(tag)
                
                # Update video
                video.tags = list(current_tags)[:20]  # Limit to 20 tags
                video.updated_at = datetime.utcnow()
                
                updated_count += 1
                
            except Exception:
                continue  # Skip videos that can't be updated
        
        if updated_count > 0:
            await self.db.commit()
        
        return updated_count


# Dependency for FastAPI
async def get_video_metadata_service(db: AsyncSession) -> VideoMetadataService:
    from server.web.app.services.video_cache_service import get_video_cache_service
    cache_service = await get_video_cache_service(db)
    return VideoMetadataService(db, cache_service)