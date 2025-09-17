"""
Tests for Discord Import Service.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# Mock discord.py to avoid import issues
with patch.dict('sys.modules', {
    'discord': Mock(),
    'discord.ext': Mock(),
    'discord.ext.commands': Mock()
}):
    from server.web.app.services.discord_import_service import DiscordImportService
from server.web.app.models import ImportJob, ImportStatus, User


class TestDiscordImportService:
    """Test cases for DiscordImportService"""
    
    @pytest.fixture
    def mock_bot(self):
        """Mock Discord bot"""
        bot = Mock()
        bot.user = Mock()
        bot.user.name = "TestBot"
        return bot
    
    @pytest.fixture
    def mock_db_session_factory(self, db_session):
        """Mock database session factory"""
        async def factory():
            return db_session
        return factory
    
    @pytest.fixture
    async def service(self, mock_bot, mock_db_session_factory):
        """Create DiscordImportService instance"""
        service = DiscordImportService(
            bot=mock_bot,
            db_session_factory=mock_db_session_factory,
            import_channel_id=123456789
        )
        await service.initialize()
        return service
    
    def test_extract_urls(self, service):
        """Test URL extraction from message text"""
        # Test YouTube URLs
        text = "Check out this video: https://youtube.com/watch?v=dQw4w9WgXcQ"
        urls = service._extract_urls(text)
        assert len(urls) == 1
        assert "youtube.com/watch?v=dQw4w9WgXcQ" in urls[0]
        
        # Test multiple URLs
        text = """
        YouTube: https://youtube.com/watch?v=test1
        TikTok: https://tiktok.com/@user/video/123
        Instagram: https://instagram.com/p/test
        """
        urls = service._extract_urls(text)
        assert len(urls) == 3
        
        # Test no URLs
        text = "This is just regular text with no URLs"
        urls = service._extract_urls(text)
        assert len(urls) == 0
    
    def test_format_duration(self, service):
        """Test duration formatting"""
        # Test seconds only
        assert service._format_duration(45) == "0:45"
        
        # Test minutes and seconds
        assert service._format_duration(125) == "2:05"
        
        # Test hours, minutes, and seconds
        assert service._format_duration(3665) == "1:01:05"
    
    def test_format_number(self, service):
        """Test number formatting with K/M suffixes"""
        assert service._format_number(500) == "500"
        assert service._format_number(1500) == "1.5K"
        assert service._format_number(1500000) == "1.5M"
        assert service._format_number(2500000) == "2.5M"
    
    def test_format_config(self, service):
        """Test configuration formatting for display"""
        # Test empty config
        config = {}
        result = service._format_config(config)
        assert result == "Default"
        
        # Test video config
        config = {"max_height": 720, "max_fps": 30}
        result = service._format_config(config)
        assert "720p" in result
        assert "30fps" in result
        
        # Test audio only config
        config = {"audio_only": True}
        result = service._format_config(config)
        assert "Audio Only" in result
    
    async def test_is_supported_url(self, service):
        """Test URL platform support detection"""
        # Mock the media import service
        with patch.object(service, 'media_import_service') as mock_service:
            mock_service.is_supported_url.return_value = True
            
            result = await service._is_supported_url("https://youtube.com/watch?v=test")
            assert result is True
            
            mock_service.is_supported_url.assert_called_once_with("https://youtube.com/watch?v=test")
    
    def test_is_import_options_message(self, service):
        """Test import options message detection"""
        # Mock message with import options embed
        message = Mock()
        embed = Mock()
        embed.title = "🎬 Media Import Options"
        message.embeds = [embed]
        
        result = service._is_import_options_message(message)
        assert result is True
        
        # Mock message without embeds
        message.embeds = []
        result = service._is_import_options_message(message)
        assert result is False
        
        # Mock message with different embed
        embed.title = "Different Title"
        message.embeds = [embed]
        result = service._is_import_options_message(message)
        assert result is False
    
    def test_extract_url_from_embed(self, service):
        """Test URL extraction from embed footer"""
        # Mock embed with URL in footer
        embed = Mock()
        embed.footer = Mock()
        embed.footer.text = "Source: https://youtube.com/watch?v=test"
        
        result = service._extract_url_from_embed(embed)
        assert result == "https://youtube.com/watch?v=test"
        
        # Mock embed without footer
        embed.footer = None
        result = service._extract_url_from_embed(embed)
        assert result is None
        
        # Mock embed with different footer text
        embed.footer = Mock()
        embed.footer.text = "Different text"
        result = service._extract_url_from_embed(embed)
        assert result is None
    
    @patch('server.web.app.services.discord_import_service.discord')
    async def test_create_import_options_embed(self, mock_discord, service):
        """Test creation of import options embed"""
        # Mock Discord Embed
        mock_embed = Mock()
        mock_discord.Embed.return_value = mock_embed
        
        # Mock media info
        media_info = Mock()
        media_info.title = "Test Video"
        media_info.platform = "YouTube"
        media_info.uploader = "Test User"
        media_info.duration = 120.0
        media_info.view_count = 1000
        media_info.thumbnail_url = "https://example.com/thumb.jpg"
        
        # Create embed
        result = await service._create_import_options_embed(media_info, "https://youtube.com/test")
        
        # Verify embed was created
        mock_discord.Embed.assert_called_once()
        assert result == mock_embed
        
        # Verify embed methods were called
        mock_embed.add_field.assert_called()
        mock_embed.set_thumbnail.assert_called_with(url="https://example.com/thumb.jpg")
        mock_embed.set_footer.assert_called_with(text="Source: https://youtube.com/test")
    
    async def test_handle_message_non_admin(self, service):
        """Test message handling for non-admin users"""
        # Mock message from non-admin user
        message = Mock()
        message.channel.id = 123456789  # Correct channel
        message.author.bot = False
        message.content = "https://youtube.com/watch?v=test"
        message.reply = AsyncMock()
        
        # Mock admin check to return False
        with patch.object(service, '_is_admin_user', return_value=False):
            await service.handle_message(message)
            
            # Verify error message was sent
            message.reply.assert_called_once_with("❌ Only administrators can use the import feature.")
    
    async def test_handle_message_wrong_channel(self, service):
        """Test message handling in wrong channel"""
        # Mock message from wrong channel
        message = Mock()
        message.channel.id = 987654321  # Wrong channel
        message.author.bot = False
        
        # Should return early without processing
        result = await service.handle_message(message)
        assert result is None
    
    async def test_handle_message_bot_user(self, service):
        """Test message handling from bot user"""
        # Mock message from bot
        message = Mock()
        message.channel.id = 123456789  # Correct channel
        message.author.bot = True
        
        # Should return early without processing
        result = await service.handle_message(message)
        assert result is None
    
    async def test_handle_message_no_urls(self, service):
        """Test message handling with no URLs"""
        # Mock message with no URLs
        message = Mock()
        message.channel.id = 123456789  # Correct channel
        message.author.bot = False
        message.content = "This is just regular text"
        
        # Mock admin check to return True
        with patch.object(service, '_is_admin_user', return_value=True):
            result = await service.handle_message(message)
            assert result is None
    
    async def test_handle_message_with_supported_url(self, service):
        """Test message handling with supported URL"""
        # Mock message with supported URL
        message = Mock()
        message.channel.id = 123456789  # Correct channel
        message.author.bot = False
        message.content = "https://youtube.com/watch?v=test"
        
        # Mock methods
        with patch.object(service, '_is_admin_user', return_value=True), \
             patch.object(service, '_is_supported_url', return_value=True), \
             patch.object(service, '_handle_import_url', new_callable=AsyncMock) as mock_handle:
            
            await service.handle_message(message)
            
            # Verify import URL handler was called
            mock_handle.assert_called_once_with(message, "https://youtube.com/watch?v=test")


# Note: The DiscordImportBot class has been removed as media import functionality
# is now integrated into the main server bot as a cog (server/server_bot/cogs/media_import.py)
# Tests for the cog functionality would be in a separate test file for the server bot cogs.