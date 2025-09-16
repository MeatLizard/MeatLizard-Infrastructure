
import pytest
from unittest.mock import patch, AsyncMock
import os

from server.web.app.services.discord_storage_service import DiscordStorageService

@pytest.mark.asyncio
@patch("aiohttp.ClientSession.post")
async def test_upload_file(mock_post):
    # Mock the response from Discord
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {"attachments": [{"url": "https://cdn.discordapp.com/attachments/..."}]}
    mock_post.return_value.__aenter__.return_value = mock_response
    
    service = DiscordStorageService(webhook_url="https://discord.com/api/webhooks/...")
    
    # Create a dummy file for testing
    file_path = "test_file.txt"
    with open(file_path, "w") as f:
        f.write("test content")
        
    result = await service.upload_file(file_path)
    
    assert "attachments" in result
    
    # Clean up the dummy file
    os.remove(file_path)
