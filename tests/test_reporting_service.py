import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.services.reporting_service import ReportingService
from server.web.app.models import User, Paste, URLShortener, ContentTypeEnum

@pytest.mark.asyncio
async def test_get_user_dashboard(db_session: AsyncSession):
    """
    Test the get_user_dashboard method of the ReportingService.
    """
    async for session in db_session:
        # Arrange
        reporting_service = ReportingService(session)
        user = User(display_label="reporting_user")
        
        paste = Paste(paste_id="reporting-paste", content="Some content", user=user, view_count=100)
        url = URLShortener(slug="reporting-url", target_url="https://example.com", user=user, click_count=200)
        
        session.add_all([user, paste, url])
        await session.commit()

        # Act
        dashboard = await reporting_service.get_user_dashboard(user)

        # Assert
        assert dashboard is not None
        assert dashboard["content_stats"][ContentTypeEnum.paste] == 1
        assert dashboard["content_stats"][ContentTypeEnum.url] == 1
        assert dashboard["paste_views"] == 100
        assert dashboard["url_clicks"] == 200