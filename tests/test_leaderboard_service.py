import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.services.leaderboard_service import LeaderboardService
from server.web.app.models import User, URLShortener, Paste

@pytest.mark.asyncio
async def test_generate_top_users_by_reputation(db_session: AsyncSession):
    """
    Test the generate_top_users_by_reputation method of the LeaderboardService.
    """
    async for session in db_session:
        # Arrange
        leaderboard_service = LeaderboardService(session)
        user1 = User(display_label="user1", reputation_score=100)
        user2 = User(display_label="user2", reputation_score=200)
        session.add_all([user1, user2])
        await session.commit()

        # Act
        leaderboard = await leaderboard_service.generate_top_users_by_reputation()

        # Assert
        assert len(leaderboard) == 2
        assert leaderboard[0].display_label == "user2"
        assert leaderboard[1].display_label == "user1"

@pytest.mark.asyncio
async def test_generate_top_urls_by_clicks(db_session: AsyncSession):
    """
    Test the generate_top_urls_by_clicks method of the LeaderboardService.
    """
    async for session in db_session:
        # Arrange
        leaderboard_service = LeaderboardService(session)
        user = User(display_label="url_user")
        url1 = URLShortener(slug="url1", target_url="https://example.com", user=user, click_count=100)
        url2 = URLShortener(slug="url2", target_url="https://example.com", user=user, click_count=200)
        session.add_all([user, url1, url2])
        await session.commit()

        # Act
        leaderboard = await leaderboard_service.generate_top_urls_by_clicks()

        # Assert
        assert len(leaderboard) == 2
        assert leaderboard[0].slug == "url2"
        assert leaderboard[1].slug == "url1"