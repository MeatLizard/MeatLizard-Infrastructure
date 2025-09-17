"""
Integration tests for error handling and recovery mechanisms.
"""
import pytest
import asyncio
import uuid
import random
from unittest.mock import AsyncMock, MagicMock, patch

from server.web.app.services.video_upload_service import VideoUploadService, VideoMetadata
from server.web.app.services.video_transcoding_service import VideoTranscodingService
from server.web.app.services.streaming_service import StreamingService
from server.web.app.models import Video, VideoStatus, User
from tests.mocks import create_mock_s3_service, create_mock_ffmpeg_service


class TestUploadErrorHandling:
    """Test error handling in upload scenarios."""
    
    @pytest.fixture
    async def mock_db(self):
        """Mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        db.refresh = AsyncMock()
        db.get = AsyncMock()
        return db
    
    @pytest.fixture
    def upload_service_with_failures(self, mock_db):
        """Create upload service with simulated failures."""
        service = VideoUploadService(mock_db)
        service.s3_service = create_mock_s3_service()
        service.analysis_service = MagicMock()
        service.analysis_service.validate_file_info = MagicMock()
        return service
    
    async def test_s3_upload_failure_recovery(self, upload_service_with_failures, mock_db):
        """Test recovery from S3 upload failures."""
        
        # Configure S3 service with 30% failure rate
        upload_service_with_failures.s3_service.set_upload_failure_rate(0.3)
        
        # Create test data
        user_id = str(uuid.uuid4())
        metadata = VideoMetadata("Failure Test Video", "Description", ["test"])
        file_info = {
            'filename': 'test.mp4',
            'size': 1024 * 1024 * 10,  # 10MB
            'total_chunks': 5
        }
        
        # Mock video
        video_id = str(uuid.uuid4())
        mock_video = Video(
            id=video_id,
            creator_id=user_id,
            title="Failure Test Video",
            status=VideoStatus.uploading
        )
        mock_db.get.return_value = mock_video
        
        # Attempt multiple uploads to test failure/recovery
        attempts = 20
        results = []
        
        for attempt in range(attempts):
            try:
                session = await upload_service_with_failures.initiate_upload(user_id, metadata, file_info)
                
                # Try to process chunks
                chunk_data = b"x" * (1024 * 1024)  # 1MB chunks
                chunk_results = []
                
                for chunk_num in range(file_info['total_chunks']):
                    try:
                        result = await upload_service_with_failures.process_chunk(
                            session.session_id, chunk_data, chunk_num + 1
                        )
                        chunk_results.append(result.success)
                    except Exception:
                        chunk_results.append(False)
                
                # Try to complete upload
                try:
                    with patch('os.path.exists', return_value=True):
                        with patch('os.rename'):
                            completed_video = await upload_service_with_failures.complete_upload(
                                session.session_id, ["720p_30fps"]
                            )
                    
                    results.append({
                        'attempt': attempt,
                        'success': True,
                        'chunks_successful': sum(chunk_results),
                        'total_chunks': len(chunk_results)
                    })
                except Exception as e:
                    results.append({
                        'attempt': attempt,
                        'success': False,
                        'error': str(e),
                        'chunks_successful': sum(chunk_results),
                        'total_chunks': len(chunk_results)
                    })
                    
            except Exception as e:
                results.append({
                    'attempt': attempt,
                    'success': False,
                    'error': str(e),
                    'chunks_successful': 0,
                    'total_chunks': 0
                })
        
        # Analyze results
        successful_uploads = [r for r in results if r['success']]
        failed_uploads = [r for r in results if not r['success']]
        
        success_rate = len(successful_uploads) / len(results)
        
        print(f"\nS3 Upload Failure Recovery Results:")
        print(f"  Total attempts: {len(results)}")
        print(f"  Successful uploads: {len(successful_uploads)}")
        print(f"  Failed uploads: {len(failed_uploads)}")
        print(f"  Success rate: {success_rate:.2%}")
        
        # With 30% failure rate, we should still have some successes
        assert success_rate > 0.4  # At least 40% should succeed despite failures
        assert len(successful_uploads) > 0  # At least some should succeed
    
    async def test_upload_cancellation_and_cleanup(self, upload_service_with_failures, mock_db):
        """Test upload cancellation and resource cleanup."""
        
        # Create multiple upload sessions
        sessions = []
        user_id = str(uuid.uuid4())
        
        for i in range(5):
            video_id = str(uuid.uuid4())
            mock_video = Video(
                id=video_id,
                creator_id=user_id,
                title=f"Cancel Test Video {i}",
                status=VideoStatus.uploading
            )
            mock_db.get.return_value = mock_video
            
            metadata = VideoMetadata(f"Cancel Test Video {i}", "Description", ["test"])
            file_info = {
                'filename': f'test_{i}.mp4',
                'size': 1024 * 1024 * 5,
                'total_chunks': 3
            }
            
            try:
                session = await upload_service_with_failures.initiate_upload(user_id, metadata, file_info)
                sessions.append(session)
            except Exception:
                pass  # Skip failed initiations
        
        # Process some chunks for each session
        for session in sessions:
            chunk_data = b"x" * (1024 * 1024)
            
            try:
                # Process partial chunks
                for chunk_num in range(2):  # Only process 2 out of 3 chunks
                    await upload_service_with_failures.process_chunk(
                        session.session_id, chunk_data, chunk_num + 1
                    )
            except Exception:
                pass  # Continue with cancellation test
        
        # Cancel all sessions
        cancellation_results = []
        
        for session in sessions:
            try:
                success = await upload_service_with_failures.cancel_upload(session.session_id)
                cancellation_results.append({'session_id': session.session_id, 'success': success})
            except Exception as e:
                cancellation_results.append({
                    'session_id': session.session_id, 
                    'success': False, 
                    'error': str(e)
                })
        
        # Verify cleanup
        successful_cancellations = [r for r in cancellation_results if r['success']]
        
        print(f"\nUpload Cancellation Results:")
        print(f"  Sessions created: {len(sessions)}")
        print(f"  Successful cancellations: {len(successful_cancellations)}")
        print(f"  Active sessions remaining: {len(upload_service_with_failures.active_sessions)}")
        
        # Assertions
        assert len(successful_cancellations) >= len(sessions) * 0.8  # 80% should cancel successfully
        assert len(upload_service_with_failures.active_sessions) == 0  # All sessions should be cleaned up
    
    async def test_database_transaction_rollback(self, upload_service_with_failures, mock_db):
        """Test database transaction rollback on errors."""
        
        # Configure database to fail on commit
        commit_failure_count = 0
        original_commit = mock_db.commit
        
        async def failing_commit():
            nonlocal commit_failure_count
            commit_failure_count += 1
            if commit_failure_count <= 2:  # Fail first 2 commits
                raise Exception("Database commit failed")
            return await original_commit()
        
        mock_db.commit = failing_commit
        
        # Attempt uploads
        user_id = str(uuid.uuid4())
        metadata = VideoMetadata("DB Failure Test", "Description", ["test"])
        file_info = {
            'filename': 'test.mp4',
            'size': 1024 * 1024 * 5,
            'total_chunks': 3
        }
        
        results = []
        
        for attempt in range(5):
            video_id = str(uuid.uuid4())
            mock_video = Video(
                id=video_id,
                creator_id=user_id,
                title="DB Failure Test",
                status=VideoStatus.uploading
            )
            mock_db.get.return_value = mock_video
            
            try:
                session = await upload_service_with_failures.initiate_upload(user_id, metadata, file_info)
                results.append({'attempt': attempt, 'success': True, 'session_id': session.session_id})
            except Exception as e:
                results.append({'attempt': attempt, 'success': False, 'error': str(e)})
        
        # Analyze results
        successful_attempts = [r for r in results if r['success']]
        failed_attempts = [r for r in results if not r['success']]
        
        print(f"\nDatabase Transaction Rollback Results:")
        print(f"  Total attempts: {len(results)}")
        print(f"  Successful (after failures): {len(successful_attempts)}")
        print(f"  Failed (during DB issues): {len(failed_attempts)}")
        print(f"  Rollback calls: {mock_db.rollback.call_count}")
        
        # Should have some failures initially, then successes
        assert len(failed_attempts) >= 2  # First 2 should fail
        assert len(successful_attempts) >= 2  # Later ones should succeed
        assert mock_db.rollback.call_count >= len(failed_attempts)  # Rollbacks should be called


class TestTranscodingErrorHandling:
    """Test error handling in transcoding scenarios."""
    
    @pytest.fixture
    async def mock_db(self):
        """Mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    @pytest.fixture
    def transcoding_service_with_failures(self, mock_db):
        """Create transcoding service with simulated failures."""
        service = VideoTranscodingService(mock_db, "redis://localhost:6379")
        service.redis_client = AsyncMock()
        return service
    
    async def test_transcoding_job_retry_mechanism(self, transcoding_service_with_failures, mock_db):
        """Test transcoding job retry mechanism."""
        
        # Create jobs with different retry counts
        jobs = [
            {
                "job_id": str(uuid.uuid4()),
                "video_id": str(uuid.uuid4()),
                "retry_count": 0  # Should be retried
            },
            {
                "job_id": str(uuid.uuid4()),
                "video_id": str(uuid.uuid4()),
                "retry_count": 2  # Should be retried
            },
            {
                "job_id": str(uuid.uuid4()),
                "video_id": str(uuid.uuid4()),
                "retry_count": 3  # Should NOT be retried (max retries reached)
            }
        ]
        
        # Mock database operations
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        
        retry_results = []
        
        for job in jobs:
            try:
                result = await transcoding_service_with_failures.fail_job(
                    job_id=job["job_id"],
                    error_message="Simulated transcoding failure",
                    job_data=job
                )
                retry_results.append({
                    'job_id': job['job_id'],
                    'retry_count': job['retry_count'],
                    'result': result,
                    'should_retry': job['retry_count'] < 3
                })
            except Exception as e:
                retry_results.append({
                    'job_id': job['job_id'],
                    'retry_count': job['retry_count'],
                    'error': str(e),
                    'should_retry': job['retry_count'] < 3
                })
        
        # Analyze retry behavior
        jobs_that_should_retry = [r for r in retry_results if r['should_retry']]
        jobs_that_should_not_retry = [r for r in retry_results if not r['should_retry']]
        
        print(f"\nTranscoding Job Retry Results:")
        print(f"  Jobs that should retry: {len(jobs_that_should_retry)}")
        print(f"  Jobs that should not retry: {len(jobs_that_should_not_retry)}")
        
        # Verify retry scheduling was called for jobs that should retry
        expected_retry_calls = len(jobs_that_should_retry)
        actual_retry_calls = transcoding_service_with_failures.redis_client.zadd.call_count
        
        print(f"  Expected retry calls: {expected_retry_calls}")
        print(f"  Actual retry calls: {actual_retry_calls}")
        
        # Assertions
        assert len(jobs_that_should_retry) == 2  # First 2 jobs should retry
        assert len(jobs_that_should_not_retry) == 1  # Last job should not retry
        assert actual_retry_calls >= expected_retry_calls * 0.8  # Most retries should be scheduled
    
    async def test_transcoding_queue_recovery(self, transcoding_service_with_failures):
        """Test transcoding queue recovery from failures."""
        
        # Simulate queue operations with intermittent failures
        queue_operations = []
        
        # Mock Redis operations with failures
        call_count = 0
        
        def failing_lpush(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Fail every 3rd operation
                raise Exception("Redis connection failed")
            return AsyncMock()
        
        transcoding_service_with_failures.redis_client.lpush.side_effect = failing_lpush
        
        # Attempt to queue multiple jobs
        for i in range(10):
            video_id = str(uuid.uuid4())
            
            try:
                job = await transcoding_service_with_failures.queue_transcoding_job(
                    video_id=video_id,
                    quality_preset="720p_30fps",
                    target_resolution="1280x720",
                    target_framerate=30,
                    target_bitrate=2500
                )
                queue_operations.append({'video_id': video_id, 'success': True})
            except Exception as e:
                queue_operations.append({'video_id': video_id, 'success': False, 'error': str(e)})
        
        # Analyze queue operations
        successful_operations = [op for op in queue_operations if op['success']]
        failed_operations = [op for op in queue_operations if not op['success']]
        
        print(f"\nTranscoding Queue Recovery Results:")
        print(f"  Total operations: {len(queue_operations)}")
        print(f"  Successful: {len(successful_operations)}")
        print(f"  Failed: {len(failed_operations)}")
        
        # Should have mix of successes and failures
        assert len(successful_operations) > 0  # Some should succeed
        assert len(failed_operations) > 0   # Some should fail (due to Redis failures)
        assert len(successful_operations) >= len(queue_operations) * 0.6  # At least 60% success
    
    async def test_processing_job_timeout_handling(self, transcoding_service_with_failures, mock_db):
        """Test handling of processing job timeouts."""
        
        # Create jobs that simulate different timeout scenarios
        jobs = []
        for i in range(5):
            job_data = {
                "job_id": str(uuid.uuid4()),
                "video_id": str(uuid.uuid4()),
                "quality_preset": "720p_30fps",
                "retry_count": 0
            }
            jobs.append(job_data)
        
        # Mock database operations
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        
        # Simulate processing with timeouts
        processing_results = []
        
        for i, job in enumerate(jobs):
            try:
                # Mark as processing
                success = await transcoding_service_with_failures.mark_job_processing(job["job_id"])
                
                if not success:
                    processing_results.append({
                        'job_id': job['job_id'],
                        'stage': 'mark_processing',
                        'success': False
                    })
                    continue
                
                # Simulate timeout on some jobs
                if i % 2 == 0:  # Timeout every other job
                    # Simulate timeout by failing the job
                    await transcoding_service_with_failures.fail_job(
                        job_id=job["job_id"],
                        error_message="Processing timeout",
                        job_data=job
                    )
                    processing_results.append({
                        'job_id': job['job_id'],
                        'stage': 'timeout',
                        'success': False,
                        'retry_scheduled': True
                    })
                else:
                    # Complete successfully
                    success = await transcoding_service_with_failures.complete_job(
                        job_id=job["job_id"],
                        output_s3_key=f"output/{job['job_id']}.mp4",
                        hls_manifest_s3_key=f"hls/{job['job_id']}/playlist.m3u8",
                        output_file_size=1024 * 1024 * 50
                    )
                    processing_results.append({
                        'job_id': job['job_id'],
                        'stage': 'completed',
                        'success': success
                    })
                    
            except Exception as e:
                processing_results.append({
                    'job_id': job['job_id'],
                    'stage': 'error',
                    'success': False,
                    'error': str(e)
                })
        
        # Analyze timeout handling
        completed_jobs = [r for r in processing_results if r.get('stage') == 'completed' and r['success']]
        timeout_jobs = [r for r in processing_results if r.get('stage') == 'timeout']
        error_jobs = [r for r in processing_results if r.get('stage') == 'error']
        
        print(f"\nProcessing Job Timeout Handling Results:")
        print(f"  Total jobs: {len(jobs)}")
        print(f"  Completed successfully: {len(completed_jobs)}")
        print(f"  Timed out (with retry): {len(timeout_jobs)}")
        print(f"  Other errors: {len(error_jobs)}")
        
        # Assertions
        assert len(completed_jobs) > 0  # Some jobs should complete
        assert len(timeout_jobs) > 0   # Some jobs should timeout
        assert len(completed_jobs) + len(timeout_jobs) >= len(jobs) * 0.8  # Most should be handled


class TestStreamingErrorHandling:
    """Test error handling in streaming scenarios."""
    
    @pytest.fixture
    async def mock_db(self):
        """Mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        db.get = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    @pytest.fixture
    def streaming_service_with_failures(self, mock_db):
        """Create streaming service with simulated failures."""
        service = StreamingService(mock_db)
        service.hls_service = MagicMock()
        return service
    
    async def test_streaming_session_recovery(self, streaming_service_with_failures, mock_db):
        """Test streaming session recovery from failures."""
        
        # Create video
        video_id = str(uuid.uuid4())
        mock_video = Video(
            id=video_id,
            creator_id=str(uuid.uuid4()),
            title="Streaming Recovery Test",
            status=VideoStatus.ready,
            duration_seconds=120
        )
        
        # Simulate database failures during session creation
        session_creation_attempts = []
        
        for attempt in range(10):
            # Randomly fail database operations
            if random.random() < 0.3:  # 30% failure rate
                mock_db.commit.side_effect = Exception("Database connection lost")
            else:
                mock_db.commit.side_effect = None
            
            try:
                session = await streaming_service_with_failures.create_viewing_session(
                    video_id=video_id,
                    user_id=str(uuid.uuid4()),
                    ip_address=f"192.168.1.{attempt}",
                    user_agent="Test Browser"
                )
                session_creation_attempts.append({
                    'attempt': attempt,
                    'success': True,
                    'session_token': session.session_token
                })
            except Exception as e:
                session_creation_attempts.append({
                    'attempt': attempt,
                    'success': False,
                    'error': str(e)
                })
        
        # Analyze session creation results
        successful_sessions = [a for a in session_creation_attempts if a['success']]
        failed_sessions = [a for a in session_creation_attempts if not a['success']]
        
        print(f"\nStreaming Session Recovery Results:")
        print(f"  Total attempts: {len(session_creation_attempts)}")
        print(f"  Successful sessions: {len(successful_sessions)}")
        print(f"  Failed sessions: {len(failed_sessions)}")
        
        # Should have mix of successes and failures
        assert len(successful_sessions) > 0  # Some should succeed
        assert len(failed_sessions) > 0   # Some should fail
        assert len(successful_sessions) >= len(session_creation_attempts) * 0.5  # At least 50% success
    
    async def test_viewing_progress_update_resilience(self, streaming_service_with_failures, mock_db):
        """Test resilience of viewing progress updates."""
        
        # Create a viewing session
        video_id = str(uuid.uuid4())
        session_token = "test-session-token"
        
        # Mock session for progress updates
        from server.web.app.models import ViewSession
        mock_session = ViewSession(
            id=str(uuid.uuid4()),
            video_id=video_id,
            session_token=session_token,
            current_position_seconds=0.0,
            total_watch_time_seconds=0.0,
            completion_percentage=0.0
        )
        
        # Simulate progress updates with intermittent failures
        progress_updates = []
        
        for position in range(0, 121, 10):  # Every 10 seconds for 2 minutes
            # Randomly fail database operations
            if random.random() < 0.2:  # 20% failure rate
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None  # Session not found
                mock_db.execute.return_value = mock_result
            else:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_session
                mock_db.execute.return_value = mock_result
                mock_db.commit.side_effect = None
            
            progress_data = {
                'current_position_seconds': float(position),
                'completion_percentage': (position / 120) * 100,
                'quality_switches': position // 30,  # Switch every 30 seconds
                'buffering_events': position // 60   # Buffer every minute
            }
            
            try:
                updated_session = await streaming_service_with_failures.update_viewing_progress(
                    session_token, video_id, progress_data
                )
                progress_updates.append({
                    'position': position,
                    'success': True,
                    'completion': progress_data['completion_percentage']
                })
            except Exception as e:
                progress_updates.append({
                    'position': position,
                    'success': False,
                    'error': str(e)
                })
        
        # Analyze progress update resilience
        successful_updates = [u for u in progress_updates if u['success']]
        failed_updates = [u for u in progress_updates if not u['success']]
        
        print(f"\nViewing Progress Update Resilience Results:")
        print(f"  Total updates: {len(progress_updates)}")
        print(f"  Successful updates: {len(successful_updates)}")
        print(f"  Failed updates: {len(failed_updates)}")
        
        # Should handle failures gracefully
        assert len(successful_updates) > 0  # Some should succeed
        assert len(successful_updates) >= len(progress_updates) * 0.7  # At least 70% success


if __name__ == "__main__":
    pytest.main([__file__, "-v"])