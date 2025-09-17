"""
Tests for Import Job Queue Service.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# Mock redis to avoid dependency issues
with patch.dict('sys.modules', {'redis.asyncio': Mock()}):
    from server.web.app.services.import_job_queue import ImportJobQueue, ImportJobManager
from server.web.app.models import ImportJob, ImportStatus, User


class TestImportJobQueue:
    """Test cases for ImportJobQueue"""
    
    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client"""
        client = Mock()
        client.blpop = AsyncMock()
        client.rpush = AsyncMock()
        client.llen = AsyncMock()
        client.close = AsyncMock()
        return client
    
    @pytest.fixture
    async def job_queue(self, db_session, mock_redis_client):
        """Create ImportJobQueue instance"""
        with patch('server.web.app.services.import_job_queue.redis.from_url', return_value=mock_redis_client):
            queue = ImportJobQueue(db_session)
            queue.redis_client = mock_redis_client
            return queue
    
    async def test_queue_job_success(self, job_queue, mock_redis_client):
        """Test successful job queuing"""
        job_id = "test-job-id"
        mock_redis_client.rpush.return_value = 1
        
        result = await job_queue.queue_job(job_id)
        
        assert result is True
        mock_redis_client.rpush.assert_called_once_with("import_jobs", job_id)
    
    async def test_queue_job_failure(self, job_queue, mock_redis_client):
        """Test job queuing failure"""
        job_id = "test-job-id"
        mock_redis_client.rpush.side_effect = Exception("Redis error")
        
        result = await job_queue.queue_job(job_id)
        
        assert result is False
    
    async def test_get_queue_length(self, job_queue, mock_redis_client):
        """Test getting queue length"""
        mock_redis_client.llen.return_value = 5
        
        length = await job_queue.get_queue_length()
        
        assert length == 5
        mock_redis_client.llen.assert_called_once_with("import_jobs")
    
    async def test_get_queue_length_error(self, job_queue, mock_redis_client):
        """Test getting queue length with error"""
        mock_redis_client.llen.side_effect = Exception("Redis error")
        
        length = await job_queue.get_queue_length()
        
        assert length == 0
    
    async def test_get_processing_jobs(self, job_queue):
        """Test getting processing jobs status"""
        # Add mock processing jobs
        job_queue.processing_jobs = {
            "job1": Mock(done=Mock(return_value=False)),
            "job2": Mock(done=Mock(return_value=True))
        }
        
        result = await job_queue.get_processing_jobs()
        
        assert result == {
            "job1": "processing",
            "job2": "completed"
        }
    
    async def test_cancel_job_success(self, job_queue):
        """Test successful job cancellation"""
        # Add mock processing job
        mock_task = Mock()
        mock_task.done.return_value = False
        mock_task.cancel = Mock()
        job_queue.processing_jobs = {"job1": mock_task}
        
        result = await job_queue.cancel_job("job1")
        
        assert result is True
        mock_task.cancel.assert_called_once()
    
    async def test_cancel_job_not_found(self, job_queue):
        """Test cancelling non-existent job"""
        result = await job_queue.cancel_job("nonexistent")
        
        assert result is False
    
    async def test_cancel_job_already_done(self, job_queue):
        """Test cancelling already completed job"""
        # Add mock completed job
        mock_task = Mock()
        mock_task.done.return_value = True
        job_queue.processing_jobs = {"job1": mock_task}
        
        result = await job_queue.cancel_job("job1")
        
        assert result is False
    
    async def test_start_stop_worker(self, job_queue, mock_redis_client):
        """Test starting and stopping worker"""
        # Mock blpop to return no jobs (timeout)
        mock_redis_client.blpop.return_value = None
        
        # Start worker in background
        worker_task = asyncio.create_task(job_queue.start_worker())
        
        # Let it run briefly
        await asyncio.sleep(0.1)
        
        # Stop worker
        await job_queue.stop_worker()
        
        # Wait for worker to finish
        try:
            await asyncio.wait_for(worker_task, timeout=1.0)
        except asyncio.TimeoutError:
            worker_task.cancel()
    
    async def test_process_job_success(self, job_queue, db_session):
        """Test successful job processing"""
        # Create test user and job
        user = User(display_label="Test User", email="test@example.com")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        job = ImportJob(
            source_url="https://youtube.com/watch?v=test",
            platform="YouTube",
            import_config={"max_height": 720},
            requested_by=user.id,
            status=ImportStatus.queued
        )
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # Mock media import service
        with patch.object(job_queue, 'media_import_service') as mock_service:
            mock_service.process_import_job = AsyncMock(return_value=True)
            
            await job_queue._process_job(str(job.id))
            
            mock_service.process_import_job.assert_called_once_with(str(job.id))
    
    async def test_process_job_failure(self, job_queue, db_session):
        """Test job processing failure"""
        # Create test user and job
        user = User(display_label="Test User", email="test@example.com")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        job = ImportJob(
            source_url="https://youtube.com/watch?v=test",
            platform="YouTube",
            import_config={"max_height": 720},
            requested_by=user.id,
            status=ImportStatus.queued
        )
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # Mock media import service to fail
        with patch.object(job_queue, 'media_import_service') as mock_service:
            mock_service.process_import_job = AsyncMock(return_value=False)
            
            await job_queue._process_job(str(job.id))
            
            mock_service.process_import_job.assert_called_once_with(str(job.id))
    
    async def test_cleanup_completed_tasks(self, job_queue):
        """Test cleanup of completed tasks"""
        # Add mock tasks
        completed_task = Mock(done=Mock(return_value=True))
        running_task = Mock(done=Mock(return_value=False))
        
        job_queue.processing_jobs = {
            "completed": completed_task,
            "running": running_task
        }
        
        await job_queue._cleanup_completed_tasks()
        
        # Only running task should remain
        assert "completed" not in job_queue.processing_jobs
        assert "running" in job_queue.processing_jobs


class TestImportJobManager:
    """Test cases for ImportJobManager"""
    
    @pytest.fixture
    def mock_db_session_factory(self, db_session):
        """Mock database session factory"""
        async def factory():
            return db_session
        return factory
    
    @pytest.fixture
    def job_manager(self, mock_db_session_factory):
        """Create ImportJobManager instance"""
        return ImportJobManager(
            db_session_factory=mock_db_session_factory,
            redis_url="redis://localhost:6379"
        )
    
    async def test_start_stop_manager(self, job_manager):
        """Test starting and stopping job manager"""
        # Mock job queue
        with patch('server.web.app.services.import_job_queue.ImportJobQueue') as mock_queue_class:
            mock_queue = Mock()
            mock_queue.start_worker = AsyncMock()
            mock_queue.stop_worker = AsyncMock()
            mock_queue_class.return_value = mock_queue
            
            # Start manager
            await job_manager.start()
            
            assert job_manager.job_queue is not None
            assert job_manager.worker_task is not None
            
            # Stop manager
            await job_manager.stop()
            
            mock_queue.stop_worker.assert_called_once()
    
    async def test_queue_job(self, job_manager):
        """Test queuing job through manager"""
        job_id = "test-job-id"
        
        # Mock job queue
        mock_queue = Mock()
        mock_queue.queue_job = AsyncMock(return_value=True)
        job_manager.job_queue = mock_queue
        
        result = await job_manager.queue_job(job_id)
        
        assert result is True
        mock_queue.queue_job.assert_called_once_with(job_id)
    
    async def test_queue_job_no_queue(self, job_manager):
        """Test queuing job when queue is not initialized"""
        result = await job_manager.queue_job("test-job-id")
        
        assert result is False
    
    async def test_get_status_running(self, job_manager):
        """Test getting status when manager is running"""
        # Mock job queue
        mock_queue = Mock()
        mock_queue.get_queue_length = AsyncMock(return_value=5)
        mock_queue.get_processing_jobs = AsyncMock(return_value={"job1": "processing"})
        job_manager.job_queue = mock_queue
        
        status = await job_manager.get_status()
        
        assert status["status"] == "running"
        assert status["queue_length"] == 5
        assert status["processing_jobs"] == {"job1": "processing"}
    
    async def test_get_status_not_running(self, job_manager):
        """Test getting status when manager is not running"""
        status = await job_manager.get_status()
        
        assert status["status"] == "not_running"


class TestImportJobIntegration:
    """Integration tests for import job processing"""
    
    async def test_full_job_lifecycle(self, db_session):
        """Test complete job lifecycle from queue to completion"""
        # Create test user
        user = User(display_label="Test User", email="test@example.com")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Create import job
        job = ImportJob(
            source_url="https://youtube.com/watch?v=test",
            platform="YouTube",
            import_config={"max_height": 720},
            requested_by=user.id,
            status=ImportStatus.queued
        )
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # Mock Redis and media import service
        with patch('server.web.app.services.import_job_queue.redis.from_url') as mock_redis, \
             patch('server.web.app.services.import_job_queue.MediaImportService') as mock_service_class:
            
            # Setup mocks
            mock_redis_client = Mock()
            mock_redis_client.blpop = AsyncMock(side_effect=[
                ("import_jobs", str(job.id).encode()),  # Return job once
                None  # Then timeout to stop worker
            ])
            mock_redis_client.rpush = AsyncMock()
            mock_redis_client.llen = AsyncMock(return_value=0)
            mock_redis_client.close = AsyncMock()
            mock_redis.return_value = mock_redis_client
            
            mock_service = Mock()
            mock_service.process_import_job = AsyncMock(return_value=True)
            mock_service_class.return_value = mock_service
            
            # Create and start job queue
            job_queue = ImportJobQueue(db_session)
            
            # Process one job
            await job_queue._process_job(str(job.id))
            
            # Verify service was called
            mock_service.process_import_job.assert_called_once_with(str(job.id))
    
    async def test_job_error_handling(self, db_session):
        """Test error handling during job processing"""
        # Create test user
        user = User(display_label="Test User", email="test@example.com")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Create import job
        job = ImportJob(
            source_url="https://youtube.com/watch?v=test",
            platform="YouTube",
            import_config={"max_height": 720},
            requested_by=user.id,
            status=ImportStatus.queued
        )
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        
        # Mock services to raise exception
        with patch('server.web.app.services.import_job_queue.redis.from_url') as mock_redis, \
             patch('server.web.app.services.import_job_queue.MediaImportService') as mock_service_class:
            
            mock_redis_client = Mock()
            mock_redis_client.close = AsyncMock()
            mock_redis.return_value = mock_redis_client
            
            mock_service = Mock()
            mock_service.process_import_job = AsyncMock(side_effect=Exception("Processing error"))
            mock_service_class.return_value = mock_service
            
            # Create job queue
            job_queue = ImportJobQueue(db_session)
            
            # Process job (should handle exception gracefully)
            await job_queue._process_job(str(job.id))
            
            # Verify service was called despite error
            mock_service.process_import_job.assert_called_once_with(str(job.id))