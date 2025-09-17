"""
Tests for Media Import Cog.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

# Mock discord.py to avoid import issues
with patch.dict('sys.modules', {
    'discord': Mock(),
    'discord.ext': Mock(),
    'discord.ext.commands': Mock()
}):
    # Import the cog after mocking discord
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent / "server" / "server_bot"))
    
    from cogs.media_import import MediaImportCog


class TestMediaImportCog:
    """Test cases for MediaImportCog"""
    
    @pytest.fixture
    def mock_bot(self):
        """Mock Discord bot"""
        bot = Mock()
        bot.user = Mock()
        bot.user.name = "TestBot"
        bot.get_guild = Mock()
        return bot
    
    @pytest.fixture
    def mock_db_session_factory(self, db_session):
        """Mock database session factory"""
        async def factory():
            return db_session
        return factory
    
    @pytest.fixture
    def media_import_cog(self, mock_bot, mock_db_session_factory):
        """Create MediaImportCog instance"""
        return MediaImportCog(
            bot=mock_bot,
            db_session_factory=mock_db_session_factory,
            import_channel_id=123456789
        )
    
    def test_cog_initialization(self, media_import_cog):
        """Test cog initialization"""
        assert media_import_cog.import_channel_id == 123456789
        assert len(media_import_cog.url_patterns) > 0
        assert len(media_import_cog.reaction_options) == 5
        assert '🎬' in media_import_cog.reaction_options
        assert '🚫' in media_import_cog.reaction_options
    
    def test_extract_urls(self, media_import_cog):
        """Test URL extraction from message text"""
        # Test YouTube URLs
        text = "Check out this video: https://youtube.com/watch?v=dQw4w9WgXcQ"
        urls = media_import_cog._extract_urls(text)
        assert len(urls) == 1
        assert "youtube.com/watch?v=dQw4w9WgXcQ" in urls[0]
        
        # Test multiple URLs
        text = """
        YouTube: https://youtube.com/watch?v=test1
        TikTok: https://tiktok.com/@user/video/123
        Instagram: https://instagram.com/p/test
        """
        urls = media_import_cog._extract_urls(text)
        assert len(urls) == 3
        
        # Test no URLs
        text = "This is just regular text with no URLs"
        urls = media_import_cog._extract_urls(text)
        assert len(urls) == 0
    
    def test_format_duration(self, media_import_cog):
        """Test duration formatting"""
        # Test seconds only
        assert media_import_cog._format_duration(45) == "0:45"
        
        # Test minutes and seconds
        assert media_import_cog._format_duration(125) == "2:05"
        
        # Test hours, minutes, and seconds
        assert media_import_cog._format_duration(3665) == "1:01:05"
    
    def test_format_number(self, media_import_cog):
        """Test number formatting with K/M suffixes"""
        assert media_import_cog._format_number(500) == "500"
        assert media_import_cog._format_number(1500) == "1.5K"
        assert media_import_cog._format_number(1500000) == "1.5M"
        assert media_import_cog._format_number(2500000) == "2.5M"
    
    def test_format_config(self, media_import_cog):
        """Test configuration formatting for display"""
        # Test empty config
        config = {}
        result = media_import_cog._format_config(config)
        assert result == "Default"
        
        # Test video config
        config = {"max_height": 720, "max_fps": 30}
        result = media_import_cog._format_config(config)
        assert "720p" in result
        assert "30fps" in result
        
        # Test audio only config
        config = {"audio_only": True}
        result = media_import_cog._format_config(config)
        assert "Audio Only" in result
    
    async def test_is_supported_url(self, media_import_cog):
        """Test URL platform support detection"""
        with patch('cogs.media_import.MediaImportService') as mock_service_class:
            mock_service = Mock()
            mock_service.is_supported_url.return_value = True
            mock_service_class.return_value = mock_service
            
            result = await media_import_cog._is_supported_url("https://youtube.com/watch?v=test")
            assert result is True
    
    def test_is_import_options_message(self, media_import_cog):
        """Test import options message detection"""
        # Mock message with import options embed
        message = Mock()
        embed = Mock()
        embed.title = "🎬 Media Import Options"
        message.embeds = [embed]
        
        result = media_import_cog._is_import_options_message(message)
        assert result is True
        
        # Mock message without embeds
        message.embeds = []
        result = media_import_cog._is_import_options_message(message)
        assert result is False
        
        # Mock message with different embed
        embed.title = "Different Title"
        message.embeds = [embed]
        result = media_import_cog._is_import_options_message(message)
        assert result is False
    
    def test_extract_url_from_embed(self, media_import_cog):
        """Test URL extraction from embed footer"""
        # Mock embed with URL in footer
        embed = Mock()
        embed.footer = Mock()
        embed.footer.text = "Source: https://youtube.com/watch?v=test"
        
        result = media_import_cog._extract_url_from_embed(embed)
        assert result == "https://youtube.com/watch?v=test"
        
        # Mock embed without footer
        embed.footer = None
        result = media_import_cog._extract_url_from_embed(embed)
        assert result is None
        
        # Mock embed with different footer text
        embed.footer = Mock()
        embed.footer.text = "Different text"
        result = media_import_cog._extract_url_from_embed(embed)
        assert result is None
    
    async def test_on_message_non_admin(self, media_import_cog):
        """Test message handling for non-admin users"""
        # Mock message from non-admin user
        message = Mock()
        message.channel.id = 123456789  # Correct channel
        message.author.bot = False
        message.content = "https://youtube.com/watch?v=test"
        message.reply = AsyncMock()
        
        # Mock admin check to return False
        with patch.object(media_import_cog, '_is_admin_user', return_value=False):
            await media_import_cog.on_message(message)
            
            # Verify error message was sent
            message.reply.assert_called_once_with("❌ Only administrators can use the import feature.")
    
    async def test_on_message_wrong_channel(self, media_import_cog):
        """Test message handling in wrong channel"""
        # Mock message from wrong channel
        message = Mock()
        message.channel.id = 987654321  # Wrong channel
        message.author.bot = False
        
        # Should return early without processing
        result = await media_import_cog.on_message(message)
        assert result is None
    
    async def test_on_message_bot_user(self, media_import_cog):
        """Test message handling from bot user"""
        # Mock message from bot
        message = Mock()
        message.channel.id = 123456789  # Correct channel
        message.author.bot = True
        
        # Should return early without processing
        result = await media_import_cog.on_message(message)
        assert result is None
    
    async def test_on_message_no_urls(self, media_import_cog):
        """Test message handling with no URLs"""
        # Mock message with no URLs
        message = Mock()
        message.channel.id = 123456789  # Correct channel
        message.author.bot = False
        message.content = "This is just regular text"
        
        # Mock admin check to return True
        with patch.object(media_import_cog, '_is_admin_user', return_value=True):
            result = await media_import_cog.on_message(message)
            assert result is None
    
    async def test_on_message_with_supported_url(self, media_import_cog):
        """Test message handling with supported URL"""
        # Mock message with supported URL
        message = Mock()
        message.channel.id = 123456789  # Correct channel
        message.author.bot = False
        message.content = "https://youtube.com/watch?v=test"
        
        # Mock methods
        with patch.object(media_import_cog, '_is_admin_user', return_value=True), \
             patch.object(media_import_cog, '_is_supported_url', return_value=True), \
             patch.object(media_import_cog, '_handle_import_url', new_callable=AsyncMock) as mock_handle:
            
            await media_import_cog.on_message(message)
            
            # Verify import URL handler was called
            mock_handle.assert_called_once_with(message, "https://youtube.com/watch?v=test")
    
    async def test_import_command_non_admin(self, media_import_cog):
        """Test import slash command for non-admin users"""
        # Mock interaction from non-admin user
        interaction = Mock()
        interaction.user = Mock()
        interaction.response.send_message = AsyncMock()
        
        # Mock admin check to return False
        with patch.object(media_import_cog, '_is_admin_user', return_value=False):
            await media_import_cog.import_command(interaction, "https://youtube.com/watch?v=test")
            
            # Verify error message was sent
            interaction.response.send_message.assert_called_once_with(
                "❌ Only administrators can use this command.", ephemeral=True
            )
    
    async def test_import_command_unsupported_url(self, media_import_cog):
        """Test import slash command with unsupported URL"""
        # Mock interaction from admin user
        interaction = Mock()
        interaction.user = Mock()
        interaction.response.send_message = AsyncMock()
        
        # Mock admin check to return True, URL check to return False
        with patch.object(media_import_cog, '_is_admin_user', return_value=True), \
             patch.object(media_import_cog, '_is_supported_url', return_value=False):
            
            await media_import_cog.import_command(interaction, "https://unsupported.com/video")
            
            # Verify error message was sent
            interaction.response.send_message.assert_called_once_with(
                "❌ Unsupported platform or invalid URL.", ephemeral=True
            )
    
    async def test_import_status_command_non_admin(self, media_import_cog):
        """Test import status command for non-admin users"""
        # Mock interaction from non-admin user
        interaction = Mock()
        interaction.user = Mock()
        interaction.response.send_message = AsyncMock()
        
        # Mock admin check to return False
        with patch.object(media_import_cog, '_is_admin_user', return_value=False):
            await media_import_cog.import_status_command(interaction)
            
            # Verify error message was sent
            interaction.response.send_message.assert_called_once_with(
                "❌ Only administrators can use this command.", ephemeral=True
            )
    
    async def test_import_status_command_no_jobs(self, media_import_cog):
        """Test import status command with no jobs"""
        # Mock interaction from admin user
        interaction = Mock()
        interaction.user = Mock()
        interaction.response.send_message = AsyncMock()
        
        # Mock admin check and service
        with patch.object(media_import_cog, '_is_admin_user', return_value=True), \
             patch('cogs.media_import.MediaImportService') as mock_service_class:
            
            mock_service = Mock()
            mock_service.get_import_jobs = AsyncMock(return_value=[])
            mock_service_class.return_value = mock_service
            
            await media_import_cog.import_status_command(interaction)
            
            # Verify no jobs message was sent
            interaction.response.send_message.assert_called_once_with(
                "No recent import jobs found.", ephemeral=True
            )
    
    async def test_is_admin_user_with_permissions(self, media_import_cog):
        """Test admin user check with permissions"""
        # Mock user with admin permissions
        user = Mock()
        user.guild_permissions = Mock()
        user.guild_permissions.administrator = True
        
        result = await media_import_cog._is_admin_user(user)
        assert result is True
    
    async def test_is_admin_user_without_permissions(self, media_import_cog):
        """Test admin user check without permissions"""
        # Mock user without admin permissions
        user = Mock()
        user.guild_permissions = Mock()
        user.guild_permissions.administrator = False
        
        result = await media_import_cog._is_admin_user(user)
        assert result is False
    
    async def test_create_import_options_embed(self, media_import_cog):
        """Test creation of import options embed"""
        # Mock Discord Embed
        with patch('cogs.media_import.discord') as mock_discord:
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
            result = await media_import_cog._create_import_options_embed(media_info, "https://youtube.com/test")
            
            # Verify embed was created
            mock_discord.Embed.assert_called_once()
            assert result == mock_embed
            
            # Verify embed methods were called
            mock_embed.add_field.assert_called()
            mock_embed.set_thumbnail.assert_called_with(url="https://example.com/thumb.jpg")
            mock_embed.set_footer.assert_called_with(text="Source: https://youtube.com/test")