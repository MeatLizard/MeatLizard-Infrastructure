"""
Tests for video transcoding service.
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.services.video_transcoding_service import VideoTranscodingService
from server.web.app.models import TranscodingJob, TranscodingStatus


@pytest.fixture
async def mock_db():
    """Mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
async def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.lpush = AsyncMock()
    redis_mock.brpop = AsyncMock()
    redis_mock.sadd = AsyncMock()
    redis_mock.srem = AsyncMock()
    redis_mock.smembers = AsyncMock()
    redis_mock.llen = AsyncMock()
    redis_mock.scard = AsyncMock()
    redis_mock.zcard = AsyncMock()
    redis_mock.zadd = AsyncMock()
    redis_mock.zrangebyscore = AsyncMock()
    redis_mock.zrem = AsyncMock()
    return redis_mock


@pytest.fixture
async def transcoding_service(mock_db, mock_redis):
    """Create transcoding service with mocked dependencies."""
    service = VideoTranscodingService(mock_db, "redis://localhost:6379")
    service.redis_client = mock_redis
    return service


class TestVideoTranscodingService:
    """Test cases for VideoTranscodingService."""
    
    async def test_queue_transcoding_job(self, transcoding_service, mock_db, mock_redis):
        """Test queuing a transcoding job."""
        # Mock database operations
        mock_job = TranscodingJob(
            id="test-job-id",
            video_id="test-video-id",
            quality_preset="720p_30fps",
            target_resolution="1280x720",
            target_framerate=30,
            target_bitrate=2500,
            status=TranscodingStatus.queued
        )
        mock_db.refresh.side_effect = lambda obj: setattr(obj, 'id', 'test-job-id')
        
        # Call the method
        job = await transcoding_service.queue_transcoding_job(
            video_id="test-video-id",
            quality_preset="720p_30fps",
            target_resolution="1280x720",
            target_framerate=30,
            target_bitrate=2500
        )
        
        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        
        # Verify Redis operations
        mock_redis.lpush.assert_called_once()
        args = mock_redis.lpush.call_args[0]
        assert args[0] == "transcoding:jobs"
        
        # Verify job data
        job_data = json.loads(args[1])
        assert job_data["video_id"] == "test-video-id"
        assert job_data["quality_preset"] == "720p_30fps"
        assert job_data["target_resolution"] == "1280x720"
        assert job_data["target_framerate"] == 30
        assert job_data["target_bitrate"] == 2500
        assert job_data["retry_count"] == 0
    
    async def test_get_next_job(self, transcoding_service, mock_redis):
        """Test getting next job from queue."""
        # Mock Redis response
        job_data = {
            "job_id": "test-job-id",
            "video_id": "test-video-id",
            "quality_preset": "720p_30fps",
            "retry_count": 0
        }
        mock_redis.brpop.side_effect = [
            None,  # No retry jobs
            ("transcoding:jobs", json.dumps(job_data))  # Main queue job
        ]
        
        # Call the method
        result = await transcoding_service.get_next_job()
        
        # Verify result
        assert result == job_data
        
        # Verify Redis operations
        assert mock_redis.brpop.call_count == 2
        mock_redis.sadd.assert_called_once_with("transcoding:processing", json.dumps(job_data))
    
    async def test_mark_job_processing(self, transcoding_service, mock_db):
        """Test marking job as processing."""
        # Mock database response
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        
        # Call the method
        result = await transcoding_service.mark_job_processing("test-job-id")
        
        # Verify result
        assert result is True
        
        # Verify database operations
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()
    
    async def test_update_job_progress(self, transcoding_service, mock_db):
        """Test updating job progress."""
        # Mock database response
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        
        # Call the method
        result = await transcoding_service.update_job_progress("test-job-id", 50)
        
        # Verify result
        assert result is True
        
        # Verify database operations
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()
    
    async def test_complete_job(self, transcoding_service, mock_db, mock_redis):
        """Test completing a job."""
        # Mock database response
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        
        # Mock Redis processing jobs
        job_data = {"job_id": "test-job-id"}
        mock_redis.smembers.return_value = [json.dumps(job_data)]
        
        # Call the method
        result = await transcoding_service.complete_job(
            job_id="test-job-id",
            output_s3_key="output/key",
            hls_manifest_s3_key="hls/manifest",
            output_file_size=1024000
        )
        
        # Verify result
        assert result is True
        
        # Verify database operations
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()
        
        # Verify Redis cleanup
        mock_redis.srem.assert_called_once()
    
    async def test_fail_job_with_retry(self, transcoding_service, mock_db, mock_redis):
        """Test failing a job that should be retried."""
        # Mock database response
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        
        # Job data with retry count below max
        job_data = {
            "job_id": "test-job-id",
            "retry_count": 1
        }
        
        # Call the method
        result = await transcoding_service.fail_job(
            job_id="test-job-id",
            error_message="Test error",
            job_data=job_data
        )
        
        # Verify result
        assert result is True
        
        # Verify retry was scheduled
        mock_redis.zadd.assert_called_once()
    
    async def test_get_queue_stats(self, transcoding_service, mock_redis):
        """Test getting queue statistics."""
        # Mock Redis responses
        mock_redis.llen.side_effect = [5, 2]  # queued, retry_queue
        mock_redis.scard.return_value = 3  # processing
        mock_redis.zcard.return_value = 1  # scheduled_retries
        
        # Call the method
        stats = await transcoding_service.get_queue_stats()
        
        # Verify result
        expected_stats = {
            "queued": 5,
            "processing": 3,
            "retry_queue": 2,
            "scheduled_retries": 1
        }
        assert stats == expected_stats
    
    async def test_process_scheduled_retries(self, transcoding_service, mock_redis):
        """Test processing scheduled retries."""
        # Mock Redis responses
        job_data = {"job_id": "test-job-id", "retry_count": 2}
        mock_redis.zrangebyscore.return_value = [json.dumps(job_data)]
        
        # Call the method
        await transcoding_service.process_scheduled_retries()
        
        # Verify Redis operations
        mock_redis.lpush.assert_called_once_with("transcoding:retry", json.dumps(job_data))
        mock_redis.zrem.assert_called_once_with("transcoding:scheduled_retries", json.dumps(job_data))


if __name__ == "__main__":
    pytest.main([__file__])