"""
Playlist management service for video platform.
"""
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from .base_service import BaseService
from ..models import VideoPlaylist, VideoPlaylistItem, Video, Channel, User, VideoVisibility
from ..dependencies import get_db


class PlaylistService(BaseService):
    """Service for managing video playlists."""
    
    async def create_playlist(
        self,
        creator_id: uuid.UUID,
        name: str,
        description: Optional[str] = None,
        channel_id: Optional[uuid.UUID] = None,
        visibility: VideoVisibility = VideoVisibility.public,
        auto_advance: bool = True,
        shuffle_enabled: bool = False
    ) -> VideoPlaylist:
        """Create a new playlist."""
        async with self.get_db_session() as db:
            # Verify channel ownership if channel_id provided
            if channel_id:
                channel_result = await db.execute(
                    select(Channel).where(
                        and_(Channel.id == channel_id, Channel.creator_id == creator_id)
                    )
                )
                if not channel_result.scalar_one_or_none():
                    raise ValueError("Channel not found or not owned by user")
            
            playlist = VideoPlaylist(
                id=uuid.uuid4(),
                creator_id=creator_id,
                channel_id=channel_id,
                name=name,
                description=description,
                visibility=visibility,
                auto_advance=auto_advance,
                shuffle_enabled=shuffle_enabled,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(playlist)
            await db.commit()
            await db.refresh(playlist)
            
            return playlist
    
    async def get_playlist_by_id(
        self,
        playlist_id: uuid.UUID,
        include_items: bool = False
    ) -> Optional[VideoPlaylist]:
        """Get playlist by ID."""
        async with self.get_db_session() as db:
            query = select(VideoPlaylist).where(VideoPlaylist.id == playlist_id)
            
            if include_items:
                query = query.options(
                    selectinload(VideoPlaylist.items).selectinload(VideoPlaylistItem.video),
                    selectinload(VideoPlaylist.creator),
                    selectinload(VideoPlaylist.channel)
                )
            else:
                query = query.options(
                    selectinload(VideoPlaylist.creator),
                    selectinload(VideoPlaylist.channel)
                )
            
            result = await db.execute(query)
            return result.scalar_one_or_none()
    
    async def get_user_playlists(
        self,
        user_id: uuid.UUID,
        include_private: bool = False,
        channel_id: Optional[uuid.UUID] = None
    ) -> List[VideoPlaylist]:
        """Get all playlists for a user."""
        async with self.get_db_session() as db:
            query = select(VideoPlaylist).where(VideoPlaylist.creator_id == user_id)
            
            if channel_id:
                query = query.where(VideoPlaylist.channel_id == channel_id)
            
            if not include_private:
                query = query.where(VideoPlaylist.visibility != VideoVisibility.private)
            
            query = query.order_by(VideoPlaylist.created_at.desc())
            
            result = await db.execute(query)
            return result.scalars().all()
    
    async def update_playlist(
        self,
        playlist_id: uuid.UUID,
        user_id: uuid.UUID,
        **updates
    ) -> Optional[VideoPlaylist]:
        """Update playlist details."""
        async with self.get_db_session() as db:
            # Get playlist and verify ownership
            playlist = await self.get_playlist_by_id(playlist_id)
            if not playlist or playlist.creator_id != user_id:
                return None
            
            # Update allowed fields
            allowed_fields = {
                'name', 'description', 'visibility', 'auto_advance',
                'shuffle_enabled', 'thumbnail_s3_key', 'channel_id'
            }
            
            for field, value in updates.items():
                if field in allowed_fields and hasattr(playlist, field):
                    setattr(playlist, field, value)
            
            playlist.updated_at = datetime.utcnow()
            
            await db.commit()
            await db.refresh(playlist)
            
            return playlist
    
    async def delete_playlist(
        self,
        playlist_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """Delete a playlist."""
        async with self.get_db_session() as db:
            # Get playlist and verify ownership
            playlist = await self.get_playlist_by_id(playlist_id)
            if not playlist or playlist.creator_id != user_id:
                return False
            
            # Delete the playlist (items will be cascade deleted)
            await db.delete(playlist)
            await db.commit()
            
            return True
    
    async def add_video_to_playlist(
        self,
        playlist_id: uuid.UUID,
        video_id: uuid.UUID,
        user_id: uuid.UUID,
        position: Optional[int] = None
    ) -> Optional[VideoPlaylistItem]:
        """Add a video to a playlist."""
        async with self.get_db_session() as db:
            # Verify playlist ownership
            playlist = await self.get_playlist_by_id(playlist_id)
            if not playlist or playlist.creator_id != user_id:
                return None
            
            # Verify video exists and user has access
            video_result = await db.execute(
                select(Video).where(Video.id == video_id)
            )
            video = video_result.scalar_one_or_none()
            if not video:
                return None
            
            # Check if video is already in playlist
            existing_result = await db.execute(
                select(VideoPlaylistItem).where(
                    and_(
                        VideoPlaylistItem.playlist_id == playlist_id,
                        VideoPlaylistItem.video_id == video_id
                    )
                )
            )
            if existing_result.scalar_one_or_none():
                raise ValueError("Video already in playlist")
            
            # Determine position
            if position is None:
                # Add to end
                max_position_result = await db.execute(
                    select(func.max(VideoPlaylistItem.position))
                    .where(VideoPlaylistItem.playlist_id == playlist_id)
                )
                max_position = max_position_result.scalar() or 0
                position = max_position + 1
            else:
                # Shift existing items if needed
                await self._shift_playlist_positions(db, playlist_id, position, 1)
            
            playlist_item = VideoPlaylistItem(
                id=uuid.uuid4(),
                playlist_id=playlist_id,
                video_id=video_id,
                position=position,
                added_at=datetime.utcnow()
            )
            
            db.add(playlist_item)
            await db.commit()
            await db.refresh(playlist_item)
            
            return playlist_item
    
    async def remove_video_from_playlist(
        self,
        playlist_id: uuid.UUID,
        video_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """Remove a video from a playlist."""
        async with self.get_db_session() as db:
            # Verify playlist ownership
            playlist = await self.get_playlist_by_id(playlist_id)
            if not playlist or playlist.creator_id != user_id:
                return False
            
            # Find and remove the item
            item_result = await db.execute(
                select(VideoPlaylistItem).where(
                    and_(
                        VideoPlaylistItem.playlist_id == playlist_id,
                        VideoPlaylistItem.video_id == video_id
                    )
                )
            )
            item = item_result.scalar_one_or_none()
            if not item:
                return False
            
            position = item.position
            await db.delete(item)
            
            # Shift remaining items down
            await self._shift_playlist_positions(db, playlist_id, position + 1, -1)
            
            await db.commit()
            return True
    
    async def reorder_playlist_items(
        self,
        playlist_id: uuid.UUID,
        user_id: uuid.UUID,
        video_positions: List[Dict[str, Any]]
    ) -> bool:
        """Reorder items in a playlist."""
        async with self.get_db_session() as db:
            # Verify playlist ownership
            playlist = await self.get_playlist_by_id(playlist_id)
            if not playlist or playlist.creator_id != user_id:
                return False
            
            # Update positions
            for item_data in video_positions:
                video_id = item_data['video_id']
                new_position = item_data['position']
                
                await db.execute(
                    select(VideoPlaylistItem)
                    .where(
                        and_(
                            VideoPlaylistItem.playlist_id == playlist_id,
                            VideoPlaylistItem.video_id == video_id
                        )
                    )
                    .update({VideoPlaylistItem.position: new_position})
                )
            
            await db.commit()
            return True
    
    async def get_playlist_items(
        self,
        playlist_id: uuid.UUID,
        viewer_user_id: Optional[uuid.UUID] = None
    ) -> List[VideoPlaylistItem]:
        """Get all items in a playlist with visibility filtering."""
        async with self.get_db_session() as db:
            query = (
                select(VideoPlaylistItem)
                .options(
                    selectinload(VideoPlaylistItem.video).selectinload(Video.creator)
                )
                .where(VideoPlaylistItem.playlist_id == playlist_id)
                .order_by(VideoPlaylistItem.position)
            )
            
            result = await db.execute(query)
            items = result.scalars().all()
            
            # Filter videos based on visibility
            filtered_items = []
            for item in items:
                video = item.video
                if viewer_user_id:
                    # User can see their own private videos
                    if (video.visibility in [VideoVisibility.public, VideoVisibility.unlisted] or
                        video.creator_id == viewer_user_id):
                        filtered_items.append(item)
                else:
                    # Anonymous users can only see public videos
                    if video.visibility == VideoVisibility.public:
                        filtered_items.append(item)
            
            return filtered_items
    
    async def get_next_video_in_playlist(
        self,
        playlist_id: uuid.UUID,
        current_video_id: uuid.UUID,
        shuffle: bool = False
    ) -> Optional[VideoPlaylistItem]:
        """Get the next video in a playlist."""
        async with self.get_db_session() as db:
            if shuffle:
                # Get random video from playlist (excluding current)
                query = (
                    select(VideoPlaylistItem)
                    .where(
                        and_(
                            VideoPlaylistItem.playlist_id == playlist_id,
                            VideoPlaylistItem.video_id != current_video_id
                        )
                    )
                    .order_by(func.random())
                    .limit(1)
                )
            else:
                # Get current position
                current_result = await db.execute(
                    select(VideoPlaylistItem.position)
                    .where(
                        and_(
                            VideoPlaylistItem.playlist_id == playlist_id,
                            VideoPlaylistItem.video_id == current_video_id
                        )
                    )
                )
                current_position = current_result.scalar_one_or_none()
                if current_position is None:
                    return None
                
                # Get next video by position
                query = (
                    select(VideoPlaylistItem)
                    .where(
                        and_(
                            VideoPlaylistItem.playlist_id == playlist_id,
                            VideoPlaylistItem.position > current_position
                        )
                    )
                    .order_by(VideoPlaylistItem.position)
                    .limit(1)
                )
            
            result = await db.execute(query)
            return result.scalar_one_or_none()
    
    async def search_playlists(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[VideoPlaylist]:
        """Search playlists by name and description."""
        async with self.get_db_session() as db:
            search_query = (
                select(VideoPlaylist)
                .options(
                    selectinload(VideoPlaylist.creator),
                    selectinload(VideoPlaylist.channel)
                )
                .where(VideoPlaylist.visibility == VideoVisibility.public)
            )
            
            if query:
                search_query = search_query.where(
                    or_(
                        VideoPlaylist.name.ilike(f"%{query}%"),
                        VideoPlaylist.description.ilike(f"%{query}%")
                    )
                )
            
            if category:
                search_query = search_query.join(Channel).where(Channel.category == category)
            
            search_query = (
                search_query
                .order_by(VideoPlaylist.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            
            result = await db.execute(search_query)
            return result.scalars().all()
    
    async def get_playlist_stats(self, playlist_id: uuid.UUID) -> Dict[str, Any]:
        """Get playlist statistics."""
        async with self.get_db_session() as db:
            # Count videos
            video_count_result = await db.execute(
                select(func.count(VideoPlaylistItem.id))
                .where(VideoPlaylistItem.playlist_id == playlist_id)
            )
            video_count = video_count_result.scalar() or 0
            
            # Calculate total duration
            duration_result = await db.execute(
                select(func.sum(Video.duration_seconds))
                .join(VideoPlaylistItem, Video.id == VideoPlaylistItem.video_id)
                .where(VideoPlaylistItem.playlist_id == playlist_id)
            )
            total_duration = duration_result.scalar() or 0
            
            return {
                'video_count': video_count,
                'total_duration_seconds': total_duration
            }
    
    async def _shift_playlist_positions(
        self,
        db: AsyncSession,
        playlist_id: uuid.UUID,
        from_position: int,
        shift_amount: int
    ) -> None:
        """Shift playlist item positions."""
        if shift_amount > 0:
            # Shifting up (making room)
            await db.execute(
                select(VideoPlaylistItem)
                .where(
                    and_(
                        VideoPlaylistItem.playlist_id == playlist_id,
                        VideoPlaylistItem.position >= from_position
                    )
                )
                .update({
                    VideoPlaylistItem.position: VideoPlaylistItem.position + shift_amount
                })
            )
        elif shift_amount < 0:
            # Shifting down (filling gap)
            await db.execute(
                select(VideoPlaylistItem)
                .where(
                    and_(
                        VideoPlaylistItem.playlist_id == playlist_id,
                        VideoPlaylistItem.position >= from_position
                    )
                )
                .update({
                    VideoPlaylistItem.position: VideoPlaylistItem.position + shift_amount
                })
            )