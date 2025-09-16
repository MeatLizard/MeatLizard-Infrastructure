import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.services.social_service import SocialService
from server.web.app.models import User, Paste, Comment, Reaction, Playlist, PlaylistItem

@pytest.mark.asyncio
async def test_add_and_delete_comment(db_session: AsyncSession):
    """
    Test that a comment can be added and deleted.
    """
    async for session in db_session:
        # Arrange
        social_service = SocialService(session)
        user = User(display_label="comment_user")
        content = Paste(paste_id="comment-paste", content="Some content", user=user)
        session.add_all([user, content])
        await session.commit()

        # Act
        comment = await social_service.add_comment(content, user, "This is a comment.")
        assert comment.text == "This is a comment."

        await social_service.delete_comment(comment)

        # Assert
        result = await session.get(Comment, comment.id)
        assert result is None

@pytest.mark.asyncio
async def test_add_and_delete_reaction(db_session: AsyncSession):
    """
    Test that a reaction can be added and deleted.
    """
    async for session in db_session:
        # Arrange
        social_service = SocialService(session)
        user = User(display_label="reaction_user")
        content = Paste(paste_id="reaction-paste", content="Some content", user=user)
        session.add_all([user, content])
        await session.commit()

        # Act
        reaction = await social_service.add_reaction(content, user, "like")
        assert reaction.reaction_type == "like"

        await social_service.delete_reaction(reaction)

        # Assert
        result = await session.get(Reaction, reaction.id)
        assert result is None

@pytest.mark.asyncio
async def test_create_update_and_delete_playlist(db_session: AsyncSession):
    """
    Test that a playlist can be created, updated, and deleted.
    """
    async for session in db_session:
        # Arrange
        social_service = SocialService(session)
        user = User(display_label="playlist_user")
        session.add(user)
        await session.commit()

        # Act
        playlist = await social_service.create_playlist(user, "My Playlist")
        assert playlist.name == "My Playlist"

        updated_playlist = await social_service.update_playlist(playlist, name="My Awesome Playlist")
        assert updated_playlist.name == "My Awesome Playlist"

        await social_service.delete_playlist(updated_playlist)

        # Assert
        result = await session.get(Playlist, playlist.id)
        assert result is None