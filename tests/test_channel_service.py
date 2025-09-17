"""
Tests for channel service.
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from server.web.app.services.channel_service import ChannelService
from server.web.app.models import Channel, VideoVisibility


class TestChannelService:
    """Test cases for ChannelService."""
    
    @pytest.fixture
    def channel_service(self):
        """Create a ChannelService instance with mocked dependencies."""
        service = ChannelService()
        service.get_db_session = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        return session
    
    @pytest.fixture
    def sample_channel(self):
        """Create a sample channel for testing."""
        return Channel(
            id=uuid.uuid4(),
            creator_id=uuid.uuid4(),
            name="Test Channel",
            description="A test channel",
            slug="test-channel",
            visibility=VideoVisibility.public,
            category="technology",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    @pytest.mark.asyncio
    async def test_create_channel_success(self, channel_service, mock_db_session, sample_channel):
        """Test successful channel creation."""
        # Setup
        channel_service.get_db_session.return_value = mock_db_session
        channel_service._generate_unique_slug = AsyncMock(return_value="test-channel")
        channel_service.get_channel_by_slug = AsyncMock(return_value=None)
        
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()
        
        # Execute
        result = await channel_service.create_channel(
            creator_id=sample_channel.creator_id,
            name=sample_channel.name,
            description=sample_channel.description,
            visibility=sample_channel.visibility,
            category=sample_channel.category
        )
        
        # Verify
        assert result.name == sample_channel.name
        assert result.description == sample_channel.description
        assert result.visibility == sample_channel.visibility
        assert result.category == sample_channel.category
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_channel_duplicate_slug(self, channel_service, sample_channel):
        """Test channel creation with duplicate slug."""
        # Setup
        channel_service.get_channel_by_slug = AsyncMock(return_value=sample_channel)
        
        # Execute & Verify
        with pytest.raises(ValueError, match="Channel slug 'test-channel' already exists"):
            await channel_service.create_channel(
                creator_id=sample_channel.creator_id,
                name=sample_channel.name,
                slug="test-channel"
            )
    
    @pytest.mark.asyncio
    async def test_get_channel_by_id_found(self, channel_service, mock_db_session, sample_channel):
        """Test getting channel by ID when it exists."""
        # Setup
        channel_service.get_db_session.return_value = mock_db_session
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_channel
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        # Execute
        result = await channel_service.get_channel_by_id(sample_channel.id)
        
        # Verify
        assert result == sample_channel
        mock_db_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_channel_by_id_not_found(self, channel_service, mock_db_session):
        """Test getting channel by ID when it doesn't exist."""
        # Setup
        channel_service.get_db_session.return_value = mock_db_session
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        # Execute
        result = await channel_service.get_channel_by_id(uuid.uuid4())
        
        # Verify
        assert result is None
        mock_db_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_channels(self, channel_service, mock_db_session, sample_channel):
        """Test getting user's channels."""
        # Setup
        channel_service.get_db_session.return_value = mock_db_session
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_channel]
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        # Execute
        result = await channel_service.get_user_channels(sample_channel.creator_id)
        
        # Verify
        assert len(result) == 1
        assert result[0] == sample_channel
        mock_db_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_channel_success(self, channel_service, sample_channel):
        """Test successful channel update."""
        # Setup
        channel_service.get_channel_by_id = AsyncMock(return_value=sample_channel)
        
        mock_db_session = AsyncMock()
        mock_db_session.__aenter__ = AsyncMock(return_value=mock_db_session)
        mock_db_session.__aexit__ = AsyncMock(return_value=None)
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()
        channel_service.get_db_session.return_value = mock_db_session
        
        # Execute
        result = await channel_service.update_channel(
            channel_id=sample_channel.id,
            user_id=sample_channel.creator_id,
            name="Updated Channel Name",
            description="Updated description"
        )
        
        # Verify
        assert result.name == "Updated Channel Name"
        assert result.description == "Updated description"
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_channel_not_owner(self, channel_service, sample_channel):
        """Test channel update by non-owner."""
        # Setup
        channel_service.get_channel_by_id = AsyncMock(return_value=sample_channel)
        
        # Execute
        result = await channel_service.update_channel(
            channel_id=sample_channel.id,
            user_id=uuid.uuid4(),  # Different user ID
            name="Updated Channel Name"
        )
        
        # Verify
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_channel_success(self, channel_service, mock_db_session, sample_channel):
        """Test successful channel deletion."""
        # Setup
        channel_service.get_channel_by_id = AsyncMock(return_value=sample_channel)
        channel_service.get_db_session.return_value = mock_db_session
        
        mock_db_session.execute = AsyncMock()
        mock_db_session.delete = AsyncMock()
        mock_db_session.commit = AsyncMock()
        
        # Execute
        result = await channel_service.delete_channel(
            channel_id=sample_channel.id,
            user_id=sample_channel.creator_id
        )
        
        # Verify
        assert result is True
        mock_db_session.delete.assert_called_once_with(sample_channel)
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_channel_not_owner(self, channel_service, sample_channel):
        """Test channel deletion by non-owner."""
        # Setup
        channel_service.get_channel_by_id = AsyncMock(return_value=sample_channel)
        
        # Execute
        result = await channel_service.delete_channel(
            channel_id=sample_channel.id,
            user_id=uuid.uuid4()  # Different user ID
        )
        
        # Verify
        assert result is False
    
    @pytest.mark.asyncio
    async def test_search_channels(self, channel_service, mock_db_session, sample_channel):
        """Test channel search functionality."""
        # Setup
        channel_service.get_db_session.return_value = mock_db_session
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_channel]
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        # Execute
        result = await channel_service.search_channels(
            query="test",
            category="technology"
        )
        
        # Verify
        assert len(result) == 1
        assert result[0] == sample_channel
        mock_db_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_channel_stats(self, channel_service, mock_db_session):
        """Test getting channel statistics."""
        # Setup
        channel_service.get_db_session.return_value = mock_db_session
        
        # Mock the count queries
        video_count_result = MagicMock()
        video_count_result.scalar.return_value = 5
        
        playlist_count_result = MagicMock()
        playlist_count_result.scalar.return_value = 3
        
        views_count_result = MagicMock()
        views_count_result.scalar.return_value = 150
        
        mock_db_session.execute = AsyncMock(side_effect=[
            video_count_result,
            playlist_count_result,
            views_count_result
        ])
        
        # Execute
        result = await channel_service.get_channel_stats(uuid.uuid4())
        
        # Verify
        assert result['video_count'] == 5
        assert result['playlist_count'] == 3
        assert result['total_views'] == 150
        assert mock_db_session.execute.call_count == 3
    
    def test_generate_unique_slug(self, channel_service):
        """Test slug generation from channel name."""
        # This would need to be tested with a real database session
        # or more complex mocking of the async database operations
        pass