"""
Integration tests for the Pastebin API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from server.web.app.main import app
from server.web.app.models import User
from server.web.app.db import get_db
from server.web.app.services.analytics_collector import AnalyticsCollector

@pytest.fixture
async def client(db_session: AsyncSession):
    """
    Provides a TestClient instance with the database dependency overridden.
    """
    async for session in db_session:
        app.dependency_overrides[get_db] = lambda: session
        app.dependency_overrides[AnalyticsCollector] = lambda: AsyncMock(spec=AnalyticsCollector)
        yield TestClient(app)
        app.dependency_overrides.clear()
        break

@pytest.mark.asyncio
async def test_create_and_get_paste(client, db_session: AsyncSession):
    """
    Tests the full flow of creating a paste and then retrieving it.
    """
    c = await anext(client)
    async for session in db_session:
        # Setup: Create a user
        user = User(display_label="api_user")
        session.add(user)
        await session.commit()

        # 1. Create the paste
        response = c.post(
            "/api/paste",
            json={
                "content": "Hello, Pastebin!",
                "title": "My Test Paste",
                "language": "python"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert "paste_id" in data
        
        paste_id = data["paste_id"]

        # 2. Retrieve the paste
        get_response = c.get(f"/p/{paste_id}")
        assert get_response.status_code == 200
        paste_data = get_response.json()
        assert paste_data["content"] == "Hello, Pastebin!"
        assert paste_data["title"] == "My Test Paste"
        break

@pytest.mark.asyncio
async def test_get_paste_not_found(client):
    """
    Tests that requesting a non-existent paste returns a 404 error.
    """
    c = await anext(client)
    response = c.get("/p/non-existent-paste")
    assert response.status_code == 404