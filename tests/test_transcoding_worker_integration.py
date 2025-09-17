"""
Integration tests for transcoding worker.
"""
import pytest
import asyncio
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

# Skip Redis import for now since it's not installed in test environment
pytest.importorskip("redis", reason="Redis not available in test environment")

from server.web.app.services.transcoding_worker import TranscodingWorker


class TestTranscodingWorkerIntegration:
    """Integration test cases for TranscodingWorker."""
    
    @patch('server.web.app.services.transcoding_worker.create_async_engine')
    @patch('server.web.app.services.transcoding_worker.sessionmaker')
    def test_worker_initialization(self, mock_sessionmaker, mock_create_engine):
        """Test worker can be initialized with proper configuration."""
        # Mock database components
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        mock_session_class = MagicMock()
        mock_sessionmaker.return_value = mock_session_class
        
        # Create worker
        worker = TranscodingWorker(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            redis_url="redis://localhost:6379",
            s3_bucket="test-bucket",
            temp_dir="/tmp/test"
        )
        
        # Verify initialization
        assert worker.database_url == "postgresql+asyncpg://test:test@localhost/test"
        assert worker.redis_url == "redis://localhost:6379"
        assert worker.s3_bucket == "test-bucket"
        assert worker.temp_dir == Path("/tmp/test")
        assert worker.running is False
        
        # Verify database setup
        mock_create_engine.assert_called_once_with("postgresql+asyncpg://test:test@localhost/test")
        mock_sessionmaker.assert_called_once()
    
    def test_temp_directory_creation(self):
        """Test that temp directory is created during initialization."""
        with tempfile.TemporaryDirectory() as temp_base:
            temp_dir = Path(temp_base) / "transcoding_test"
            
            # Ensure directory doesn't exist initially
            assert not temp_dir.exists()
            
            # Create worker
            with patch('server.web.app.services.transcoding_worker.create_async_engine'), \
                 patch('server.web.app.services.transcoding_worker.sessionmaker'):
                worker = TranscodingWorker(
                    database_url="postgresql+asyncpg://test:test@localhost/test",
                    temp_dir=str(temp_dir)
                )
            
            # Verify directory was created
            assert temp_dir.exists()
            assert temp_dir.is_dir()
    
    @patch('server.web.app.services.transcoding_worker.create_async_engine')
    @patch('server.web.app.services.transcoding_worker.sessionmaker')
    async def test_cleanup_temp_files(self, mock_sessionmaker, mock_create_engine):
        """Test cleanup of temporary files."""
        with tempfile.TemporaryDirectory() as temp_base:
            temp_dir = Path(temp_base) / "transcoding_test"
            temp_dir.mkdir()
            
            # Create worker
            worker = TranscodingWorker(
                database_url="postgresql+asyncpg://test:test@localhost/test",
                temp_dir=str(temp_dir)
            )
            
            # Create some test files
            job_id = "test-job-123"
            test_files = [
                temp_dir / f"{job_id}_input.mp4",
                temp_dir / f"{job_id}_output.mp4",
            ]
            test_dir = temp_dir / f"{job_id}_hls"
            test_dir.mkdir()
            
            for file_path in test_files:
                file_path.write_text("test content")
            
            # Verify files exist
            for file_path in test_files:
                assert file_path.exists()
            assert test_dir.exists()
            
            # Call cleanup
            await worker._cleanup_temp_files(job_id)
            
            # Verify files are removed
            for file_path in test_files:
                assert not file_path.exists()
            assert not test_dir.exists()


if __name__ == "__main__":
    pytest.main([__file__])