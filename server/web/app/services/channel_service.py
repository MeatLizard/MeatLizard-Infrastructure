"""
Channel management service for video platform.
"""
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from .base_service import BaseService
from ..models import Channel, Video, VideoPlaylist, User, VideoVisibility
from ..dependencies import get_db


class ChannelService(BaseService):
    """Service for managing video channels."""
    
    async def create_channel(
        self,
        creator_id: uuid.UUID,
        name: str,
        description: Optional[str] = None,
        slug: Optional[str] = None,
        visibility: VideoVisibility = VideoVisibility.public,
        category: Optional[str] = None
    ) -> Channel:
        """Create a new channel."""
        async with self.get_db_session() as db:
            # Generate slug if not provided
            if not slug:
                slug = await self._generate_unique_slug(db, name)
            else:
                # Validate slug is unique
                existing = await self.get_channel_by_slug(slug)
                if existing:
                    raise ValueError(f"Channel slug '{slug}' already exists")
            
            channel = Channel(
                id=uuid.uuid4(),
                creator_id=creator_id,
                name=name,
                description=description,
                slug=slug,
                visibility=visibility,
                category=category,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(channel)
            await db.commit()
            await db.refresh(channel)
            
            return channel
    
    async def get_channel_by_id(self, channel_id: uuid.UUID) -> Optional[Channel]:
        """Get channel by ID."""
        async with self.get_db_session() as db:
            result = await db.execute(
                select(Channel)
                .options(selectinload(Channel.creator))
                .where(Channel.id == channel_id)
            )
            return result.scalar_one_or_none()
    
    async def get_channel_by_slug(self, slug: str) -> Optional[Channel]:
        """Get channel by slug."""
        async with self.get_db_session() as db:
            result = await db.execute(
                select(Channel)
                .options(selectinload(Channel.creator))
                .where(Channel.slug == slug)
            )
            return result.scalar_one_or_none()
    
    async def get_user_channels(
        self,
        user_id: uuid.UUID,
        include_private: bool = False
    ) -> List[Channel]:
        """Get all channels for a user."""
        async with self.get_db_session() as db:
            query = select(Channel).where(Channel.creator_id == user_id)
            
            if not include_private:
                query = query.where(Channel.visibility != VideoVisibility.private)
            
            query = query.order_by(Channel.created_at.desc())
            
            result = await db.execute(query)
            return result.scalars().all()
    
    async def update_channel(
        self,
        channel_id: uuid.UUID,
        user_id: uuid.UUID,
        **updates
    ) -> Optional[Channel]:
        """Update channel details."""
        async with self.get_db_session() as db:
            # Get channel and verify ownership
            channel = await self.get_channel_by_id(channel_id)
            if not channel or channel.creator_id != user_id:
                return None
            
            # Update allowed fields
            allowed_fields = {
                'name', 'description', 'visibility', 'category',
                'banner_s3_key', 'avatar_s3_key'
            }
            
            for field, value in updates.items():
                if field in allowed_fields and hasattr(channel, field):
                    setattr(channel, field, value)
            
            channel.updated_at = datetime.utcnow()
            
            await db.commit()
            await db.refresh(channel)
            
            return channel
    
    async def delete_channel(
        self,
        channel_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """Delete a channel and reassign videos to no channel."""
        async with self.get_db_session() as db:
            # Get channel and verify ownership
            channel = await self.get_channel_by_id(channel_id)
            if not channel or channel.creator_id != user_id:
                return False
            
            # Update videos to remove channel assignment
            await db.execute(
                select(Video)
                .where(Video.channel_id == channel_id)
                .update({Video.channel_id: None})
            )
            
            # Delete the channel (playlists will be cascade deleted)
            await db.delete(channel)
            await db.commit()
            
            return True
    
    async def get_channel_videos(
        self,
        channel_id: uuid.UUID,
        viewer_user_id: Optional[uuid.UUID] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Video]:
        """Get videos in a channel with visibility filtering."""
        async with self.get_db_session() as db:
            query = (
                select(Video)
                .options(selectinload(Video.creator))
                .where(Video.channel_id == channel_id)
            )
            
            # Apply visibility filtering
            if viewer_user_id:
                # User can see their own private videos
                query = query.where(
                    or_(
                        Video.visibility.in_([VideoVisibility.public, VideoVisibility.unlisted]),
                        Video.creator_id == viewer_user_id
                    )
                )
            else:
                # Anonymous users can only see public videos
                query = query.where(Video.visibility == VideoVisibility.public)
            
            query = (
                query
                .order_by(Video.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            
            result = await db.execute(query)
            return result.scalars().all()
    
    async def get_channel_playlists(
        self,
        channel_id: uuid.UUID,
        viewer_user_id: Optional[uuid.UUID] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[VideoPlaylist]:
        """Get playlists in a channel with visibility filtering."""
        async with self.get_db_session() as db:
            query = (
                select(VideoPlaylist)
                .options(selectinload(VideoPlaylist.creator))
                .where(VideoPlaylist.channel_id == channel_id)
            )
            
            # Apply visibility filtering
            if viewer_user_id:
                # User can see their own private playlists
                query = query.where(
                    or_(
                        VideoPlaylist.visibility.in_([VideoVisibility.public, VideoVisibility.unlisted]),
                        VideoPlaylist.creator_id == viewer_user_id
                    )
                )
            else:
                # Anonymous users can only see public playlists
                query = query.where(VideoPlaylist.visibility == VideoVisibility.public)
            
            query = (
                query
                .order_by(VideoPlaylist.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            
            result = await db.execute(query)
            return result.scalars().all()
    
    async def search_channels(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Channel]:
        """Search channels by name and description."""
        async with self.get_db_session() as db:
            search_query = (
                select(Channel)
                .options(selectinload(Channel.creator))
                .where(Channel.visibility == VideoVisibility.public)
            )
            
            if query:
                search_query = search_query.where(
                    or_(
                        Channel.name.ilike(f"%{query}%"),
                        Channel.description.ilike(f"%{query}%")
                    )
                )
            
            if category:
                search_query = search_query.where(Channel.category == category)
            
            search_query = (
                search_query
                .order_by(Channel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            
            result = await db.execute(search_query)
            return result.scalars().all()
    
    async def get_channel_stats(self, channel_id: uuid.UUID) -> Dict[str, Any]:
        """Get channel statistics."""
        async with self.get_db_session() as db:
            # Count videos
            video_count_result = await db.execute(
                select(func.count(Video.id))
                .where(Video.channel_id == channel_id)
            )
            video_count = video_count_result.scalar() or 0
            
            # Count playlists
            playlist_count_result = await db.execute(
                select(func.count(VideoPlaylist.id))
                .where(VideoPlaylist.channel_id == channel_id)
            )
            playlist_count = playlist_count_result.scalar() or 0
            
            # Get total views (sum of all video view sessions)
            from ..models import ViewSession
            total_views_result = await db.execute(
                select(func.count(ViewSession.id))
                .join(Video, ViewSession.video_id == Video.id)
                .where(Video.channel_id == channel_id)
            )
            total_views = total_views_result.scalar() or 0
            
            return {
                'video_count': video_count,
                'playlist_count': playlist_count,
                'total_views': total_views
            }
    
    async def _generate_unique_slug(self, db: AsyncSession, name: str) -> str:
        """Generate a unique slug from channel name."""
        import re
        
        # Create base slug from name
        base_slug = re.sub(r'[^a-zA-Z0-9\-_]', '-', name.lower())
        base_slug = re.sub(r'-+', '-', base_slug).strip('-')
        
        if not base_slug:
            base_slug = 'channel'
        
        # Check if base slug is unique
        result = await db.execute(
            select(Channel.slug).where(Channel.slug == base_slug)
        )
        
        if not result.scalar_one_or_none():
            return base_slug
        
        # Generate numbered variants
        counter = 1
        while True:
            candidate_slug = f"{base_slug}-{counter}"
            result = await db.execute(
                select(Channel.slug).where(Channel.slug == candidate_slug)
            )
            
            if not result.scalar_one_or_none():
                return candidate_slug
            
            counter += 1