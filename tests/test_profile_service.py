import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.services.profile_service import ProfileService
from server.web.app.models import User, Paste, URLShortener, ContentTypeEnum

@pytest.mark.asyncio
async def test_get_user_profile(db_session: AsyncSession):
    """
    Test the get_user_profile method of the ProfileService.
    """
    async for session in db_session:
        # Arrange
        profile_service = ProfileService(session)
        user = User(display_label="profile_user", reputation_score=100, experience_points=1000)
        
        paste = Paste(paste_id="profile-paste", content="Some content", user=user)
        url = URLShortener(slug="profile-url", target_url="https://example.com", user=user)
        
        session.add_all([user, paste, url])
        await session.commit()

        # Act
        profile = await profile_service.get_user_profile(user.id)

        # Assert
        assert profile is not None
        assert profile["user"].id == user.id
        assert profile["stats"]["reputation"] == 100
        assert profile["stats"]["xp"] == 1000
        
        assert len(profile["content"][ContentTypeEnum.paste]) == 1
        assert profile["content"][ContentTypeEnum.paste][0].paste_id == "profile-paste"
        
        assert len(profile["content"][ContentTypeEnum.url]) == 1
        assert profile["content"][ContentTypeEnum.url][0].slug == "profile-url"