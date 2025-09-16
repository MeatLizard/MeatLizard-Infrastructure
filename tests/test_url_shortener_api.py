"""
Integration tests for the URL Shortener API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.main import app
from server.web.app.models import User
from server.web.app.db import get_db

@pytest.fixture
async def client(db_session: AsyncSession):
    """
    Provides a TestClient instance with the database dependency overridden.
    """
    async for session in db_session:
        app.dependency_overrides[get_db] = lambda: session
        yield TestClient(app)
        app.dependency_overrides.clear()
        break

@pytest.mark.asyncio
async def test_create_and_redirect(client, db_session: AsyncSession):
    """
    Tests the full flow of creating a short URL and then redirecting to it.
    """
    c = await anext(client)
    async for session in db_session:
        # Setup: Create a user to own the URL
        user = User(display_label="api_user")
        session.add(user)
        await session.commit()

        # 1. Create the short URL
        response = c.post(
            "/api/shorten",
            json={"target_url": "https://example.com/very/long/path"}
        )
        assert response.status_code == 201
        data = response.json()
        assert "short_url" in data
        
        slug = data["short_url"].split("/")[-1]

        # 2. Redirect to the short URL
        redirect_response = c.get(f"/{slug}", follow_redirects=False)
        
        assert redirect_response.status_code == 307
        assert redirect_response.headers["location"] == "https://example.com/very/long/path"
        break

@pytest.mark.asyncio
async def test_redirect_not_found(client):
    """
    Tests that requesting a non-existent slug returns a 404 error.
    """
    c = await anext(client)
    response = c.get("/non-existent-slug", follow_redirects=False)
    assert response.status_code == 404
