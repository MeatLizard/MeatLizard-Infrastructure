
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from server.web.app.models import Comment, Reaction, Playlist, PlaylistItem, User, Content

class SocialService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_comment(self, content: Content, user: User, text: str) -> Comment:
        comment = Comment(
            parent_content_id=content.id,
            user_id=user.id,
            text=text
        )
        self.db.add(comment)
        await self.db.commit()
        return comment

    async def delete_comment(self, comment: Comment):
        await self.db.delete(comment)
        await self.db.commit()

    async def add_reaction(self, content: Content, user: User, reaction_type: str) -> Reaction:
        reaction = Reaction(
            content_id=content.id,
            user_id=user.id,
            reaction_type=reaction_type
        )
        self.db.add(reaction)
        await self.db.commit()
        return reaction

    async def delete_reaction(self, reaction: Reaction):
        await self.db.delete(reaction)
        await self.db.commit()

    async def create_playlist(self, user: User, name: str, description: str = None) -> Playlist:
        playlist = Playlist(
            user_id=user.id,
            name=name,
            description=description
        )
        self.db.add(playlist)
        await self.db.commit()
        return playlist

    async def update_playlist(self, playlist: Playlist, name: str = None, description: str = None) -> Playlist:
        if name:
            playlist.name = name
        if description:
            playlist.description = description
        self.db.add(playlist)
        await self.db.commit()
        return playlist

    async def delete_playlist(self, playlist: Playlist):
        await self.db.delete(playlist)
        await self.db.commit()

    async def add_to_playlist(self, playlist: Playlist, media_file: Content):
        # In a real app, you would check for duplicates and handle position
        item = PlaylistItem(
            playlist_id=playlist.id,
            media_file_id=media_file.id,
            position=len(playlist.items) + 1
        )
        self.db.add(item)
        await self.db.commit()
        return item

    async def remove_from_playlist(self, item: PlaylistItem):
        await self.db.delete(item)
        await self.db.commit()
