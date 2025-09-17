"""
Integration tests for complete video workflow.
"""
import pytest
import asyncio
import uuid
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from server.web.app.services.video_upload_service import VideoUploadService, VideoMetadata
from server.web.app.services.video_analysis_service import VideoAnalysisService
from server.web.app.services.video_transcoding_service import VideoTranscodingService
from server.web.app.services.streaming_service import StreamingService
from server.web.app.services.thumbnail_service import ThumbnailService
from server.web.app.services.video_metadata_service import VideoMetadataService
from server.web.app.models import Video, VideoStatus, User
from tests.mocks import create_mock_s3_service, create_mock_ffmpeg_service


class TestVideoWorkflowIntegration:
    """Integration tests for complete video workflow from upload to streaming."""
    
    @pytest.fixture
    async def mock_db(self):
        """Mock database session for integration tests."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.get = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    @pytest.fixture
    def mock_services(self):
        """Mock external services."""
        return {
            's3_service': create_mock_s3_service(),
            'ffmpeg_service': create_mock_ffmpeg_service()
        }
    
    @pytest.fixture
    def sample_user(self):
        """Sample user for testing."""
        return User(
            id=str(uuid.uuid4()),
            display_label="Test User"
        )
    
    @pytest.fixture
    def sample_video_file(self):
        """Create a temporary video file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            # Write mock video data
            f.write(b"mock video data" * 1000)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    async def test_complete_video_upload_workflow(self, mock_db, mock_services, sample_user, sample_video_file):
        """Test complete video upload workflow from initiation to completion."""
        
        # Setup services
        upload_service = VideoUploadService(mock_db)
        upload_service.s3_service = mock_services['s3_service']
        upload_service.analysis_service = VideoAnalysisService()
        upload_service.analysis_service.ffprobe_path = "mock-ffprobe"
        
        # Mock video creation
        video_id = str(uuid.uuid4())
        mock_video = Video(
            id=video_id,
            creator_id=sample_user.id,
            title="Test Video",
            status=VideoStatus.uploading
        )
        mock_db.get.return_value = mock_video
        
        # Mock analysis result
        with patch.object(upload_service.analysis_service, 'analyze_video_file') as mock_analyze:
            mock_analyze.return_value.is_valid = True
            mock_analyze.return_value.duration_seconds = 120.0
            mock_analyze.return_value.width = 1920
            mock_analyze.return_value.height = 1080
            
            # Step 1: Initiate upload
            metadata = VideoMetadata("Test Video", "Description", ["test"])
            file_info = {
                'filename': 'test.mp4',
                'size': os.path.getsize(sample_video_file),
                'total_chunks': 5
            }
            
            session = await upload_service.initiate_upload(sample_user.id, metadata, file_info)
            
            # Verify session created
            assert session is not None
            assert session.video_id == video_id
            assert session.user_id == sample_user.id
            
            # Step 2: Upload chunks
            chunk_size = file_info['size'] // file_info['total_chunks']
            
            with open(sample_video_file, 'rb') as f:
                for i in range(file_info['total_chunks']):
                    chunk_data = f.read(chunk_size)
                    if chunk_data:
                        result = await upload_service.process_chunk(session.session_id, chunk_data, i + 1)
                        assert result.success is True
            
            # Step 3: Complete upload
            quality_presets = ["720p_30fps", "1080p_30fps"]
            
            with patch('os.path.exists', return_value=True):
                with patch('os.rename'):
                    completed_video = await upload_service.complete_upload(session.session_id, quality_presets)
            
            # Verify completion
            assert completed_video is not None
            assert completed_video.status == VideoStatus.processing
            
            # Verify database operations
            mock_db.commit.assert_called()
    
    async def test_video_transcoding_workflow(self, mock_db, mock_services):
        """Test video transcoding workflow."""
        
        # Setup transcoding service
        transcoding_service = VideoTranscodingService(mock_db, "redis://localhost:6379")
        transcoding_service.redis_client = AsyncMock()
        
        # Mock video
        video_id = str(uuid.uuid4())
        
        # Step 1: Queue transcoding job
        job = await transcoding_service.queue_transcoding_job(
            video_id=video_id,
            quality_preset="720p_30fps",
            target_resolution="1280x720",
            target_framerate=30,
            target_bitrate=2500
        )
        
        # Verify job queued
        transcoding_service.redis_client.lpush.assert_called_once()
        
        # Step 2: Process job
        mock_job_data = {
            "job_id": str(uuid.uuid4()),
            "video_id": video_id,
            "quality_preset": "720p_30fps",
            "retry_count": 0
        }
        
        transcoding_service.redis_client.brpop.return_value = ("queue", str(mock_job_data))
        
        next_job = await transcoding_service.get_next_job()
        assert next_job is not None
        
        # Step 3: Mark as processing
        job_id = mock_job_data["job_id"]
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        
        success = await transcoding_service.mark_job_processing(job_id)
        assert success is True
        
        # Step 4: Update progress
        success = await transcoding_service.update_job_progress(job_id, 50)
        assert success is True
        
        # Step 5: Complete job
        success = await transcoding_service.complete_job(
            job_id=job_id,
            output_s3_key="output/key",
            hls_manifest_s3_key="hls/manifest",
            output_file_size=1024000
        )
        assert success is True
    
    async def test_video_streaming_workflow(self, mock_db, sample_user):
        """Test video streaming workflow."""
        
        # Setup streaming service
        streaming_service = StreamingService(mock_db)
        streaming_service.hls_service = MagicMock()
        
        # Mock video
        video_id = str(uuid.uuid4())
        mock_video = Video(
            id=video_id,
            creator_id=sample_user.id,
            title="Test Video",
            status=VideoStatus.ready,
            duration_seconds=120
        )
        mock_db.get.return_value = mock_video
        
        # Step 1: Check access
        has_access = await streaming_service.check_video_access(video_id, sample_user.id)
        assert has_access is True
        
        # Step 2: Create viewing session
        session = await streaming_service.create_viewing_session(
            video_id=video_id,
            user_id=sample_user.id,
            ip_address="192.168.1.1",
            user_agent="Test Browser"
        )
        
        assert session is not None
        assert session.video_id == video_id
        assert session.user_id == sample_user.id
        
        # Step 3: Get streaming manifest
        streaming_service.hls_service.get_available_qualities.return_value = [
            {"quality_preset": "720p_30fps", "height": 720},
            {"quality_preset": "1080p_30fps", "height": 1080}
        ]
        
        with patch.object(streaming_service, 'generate_signed_streaming_url') as mock_sign:
            mock_sign.return_value = "https://cdn.example.com/signed/url"
            
            manifest = await streaming_service.get_streaming_manifest(
                video_id=video_id,
                user_id=sample_user.id,
                session_token=session.session_token
            )
        
        assert manifest is not None
        assert manifest["video_id"] == video_id
        assert len(manifest["qualities"]) == 2
        
        # Step 4: Update viewing progress
        progress_data = {
            'current_position_seconds': 60.0,
            'completion_percentage': 50.0,
            'quality_switches': 1,
            'buffering_events': 0
        }
        
        # Mock session retrieval
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        mock_db.execute.return_value = mock_result
        
        updated_session = await streaming_service.update_viewing_progress(
            session.session_token, video_id, progress_data
        )
        
        assert updated_session.current_position_seconds == 60.0
        assert updated_session.completion_percentage == 50.0
    
    async def test_thumbnail_generation_workflow(self, mock_db, sample_user, sample_video_file):
        """Test thumbnail generation workflow."""
        
        # Setup thumbnail service
        thumbnail_service = ThumbnailService(mock_db)
        thumbnail_service.s3_service = create_mock_s3_service()
        
        # Mock video
        video_id = str(uuid.uuid4())
        mock_video = Video(
            id=video_id,
            creator_id=sample_user.id,
            title="Test Video",
            duration_seconds=120
        )
        mock_db.get.return_value = mock_video
        
        # Mock FFmpeg
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            mock_subprocess.return_value = mock_process
            
            with patch('os.path.exists', return_value=True):
                with patch('os.path.getsize', return_value=15000):
                    with patch('os.makedirs'):
                        # Generate thumbnails
                        thumbnails = await thumbnail_service.generate_thumbnails_for_video(
                            video_id=video_id,
                            video_path=sample_video_file,
                            timestamps=[12.0, 30.0, 60.0, 90.0, 108.0]
                        )
        
        # Verify thumbnails generated
        assert len(thumbnails) == 5
        assert all(thumb.timestamp > 0 for thumb in thumbnails)
        assert any(thumb.is_selected for thumb in thumbnails)  # One should be selected
        
        # Test thumbnail selection
        with patch.object(thumbnail_service, 'get_video_thumbnails') as mock_get:
            mock_thumbnails = [
                MagicMock(timestamp=30.0, filename="thumb_01.jpg")
            ]
            mock_get.return_value = mock_thumbnails
            
            selected = await thumbnail_service.select_thumbnail(
                video_id, 30.0, sample_user.id
            )
            
            assert selected is not None
    
    async def test_concurrent_upload_workflow(self, mock_db, mock_services, sample_user):
        """Test concurrent upload handling."""
        
        # Setup upload service
        upload_service = VideoUploadService(mock_db)
        upload_service.s3_service = mock_services['s3_service']
        upload_service.analysis_service = MagicMock()
        upload_service.analysis_service.validate_file_info = MagicMock()
        
        # Create multiple concurrent uploads
        concurrent_uploads = 5
        upload_tasks = []
        
        for i in range(concurrent_uploads):
            metadata = VideoMetadata(f"Test Video {i}", f"Description {i}", ["test"])
            file_info = {
                'filename': f'test_{i}.mp4',
                'size': 1024 * 1024 * 10,  # 10MB
                'total_chunks': 5
            }
            
            # Mock video for each upload
            video_id = str(uuid.uuid4())
            mock_video = Video(
                id=video_id,
                creator_id=sample_user.id,
                title=f"Test Video {i}",
                status=VideoStatus.uploading
            )
            
            # Create upload task
            async def create_upload(vid_id, meta, file_inf):
                mock_db.get.return_value = Video(
                    id=vid_id,
                    creator_id=sample_user.id,
                    title=meta.title,
                    status=VideoStatus.uploading
                )
                return await upload_service.initiate_upload(sample_user.id, meta, file_inf)
            
            task = create_upload(video_id, metadata, file_info)
            upload_tasks.append(task)
        
        # Execute concurrent uploads
        results = await asyncio.gather(*upload_tasks, return_exceptions=True)
        
        # Verify results
        successful_uploads = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_uploads) >= concurrent_uploads * 0.8  # At least 80% success
        
        # Verify each session is unique
        session_ids = [session.session_id for session in successful_uploads]
        assert len(set(session_ids)) == len(successful_uploads)  # All unique
    
    async def test_error_handling_and_recovery(self, mock_db, mock_services, sample_user):
        """Test error handling and recovery mechanisms."""
        
        # Setup services with failure simulation
        upload_service = VideoUploadService(mock_db)
        upload_service.s3_service = mock_services['s3_service']
        upload_service.analysis_service = MagicMock()
        upload_service.analysis_service.validate_file_info = MagicMock()
        
        # Test 1: Upload failure recovery
        mock_services['s3_service'].set_upload_failure_rate(0.5)  # 50% failure rate
        
        metadata = VideoMetadata("Test Video", "Description", ["test"])
        file_info = {
            'filename': 'test.mp4',
            'size': 1024 * 1024 * 10,
            'total_chunks': 5
        }
        
        # Mock video
        video_id = str(uuid.uuid4())
        mock_video = Video(
            id=video_id,
            creator_id=sample_user.id,
            title="Test Video",
            status=VideoStatus.uploading
        )
        mock_db.get.return_value = mock_video
        
        # Attempt multiple uploads (some should fail, some succeed)
        attempts = 10
        results = []
        
        for _ in range(attempts):
            try:
                session = await upload_service.initiate_upload(sample_user.id, metadata, file_info)
                results.append(session)
            except Exception as e:
                results.append(e)
        
        # Should have mix of successes and failures
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]
        
        assert len(successes) > 0  # Some should succeed
        assert len(failures) > 0   # Some should fail
        
        # Test 2: Transcoding failure and retry
        transcoding_service = VideoTranscodingService(mock_db, "redis://localhost:6379")
        transcoding_service.redis_client = AsyncMock()
        
        job_data = {
            "job_id": str(uuid.uuid4()),
            "video_id": video_id,
            "retry_count": 1  # Below max retries
        }
        
        # Mock retry scheduling
        transcoding_service.redis_client.zadd = AsyncMock()
        
        # Fail job (should schedule retry)
        result = await transcoding_service.fail_job(
            job_id=job_data["job_id"],
            error_message="Test error",
            job_data=job_data
        )
        
        assert result is True
        transcoding_service.redis_client.zadd.assert_called_once()  # Retry scheduled
    
    async def test_load_testing_scenario(self, mock_db, mock_services):
        """Test system under load."""
        
        # Setup services
        streaming_service = StreamingService(mock_db)
        
        # Create multiple videos
        video_count = 20
        videos = []
        
        for i in range(video_count):
            video = Video(
                id=str(uuid.uuid4()),
                creator_id=str(uuid.uuid4()),
                title=f"Load Test Video {i}",
                status=VideoStatus.ready,
                duration_seconds=120
            )
            videos.append(video)
        
        # Simulate concurrent access checks
        concurrent_requests = 50
        
        async def check_video_access(video):
            mock_db.get.return_value = video
            return await streaming_service.check_video_access(video.id)
        
        # Create tasks for concurrent access
        tasks = []
        for _ in range(concurrent_requests):
            video = videos[_ % len(videos)]  # Distribute across videos
            task = check_video_access(video)
            tasks.append(task)
        
        # Execute concurrent requests
        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = asyncio.get_event_loop().time()
        
        # Analyze results
        successful_requests = [r for r in results if r is True]
        failed_requests = [r for r in results if isinstance(r, Exception)]
        
        total_time = end_time - start_time
        throughput = len(successful_requests) / total_time
        
        # Performance assertions
        assert len(successful_requests) >= concurrent_requests * 0.9  # 90% success rate
        assert throughput > 10  # At least 10 requests per second
        assert total_time < 10  # Complete within 10 seconds
        
        print(f"Load test results:")
        print(f"  Successful requests: {len(successful_requests)}/{concurrent_requests}")
        print(f"  Failed requests: {len(failed_requests)}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Throughput: {throughput:.2f} req/s")


class TestVideoServiceIntegration:
    """Integration tests for video service interactions."""
    
    @pytest.fixture
    async def mock_db(self):
        """Mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.get = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    async def test_metadata_and_upload_integration(self, mock_db):
        """Test integration between metadata and upload services."""
        
        # Setup services
        metadata_service = VideoMetadataService(mock_db)
        upload_service = VideoUploadService(mock_db)
        
        # Mock user and video
        user_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())
        
        mock_video = Video(
            id=video_id,
            creator_id=user_id,
            title="Original Title",
            description="Original Description",
            tags=["original"]
        )
        
        mock_user = User(
            id=user_id,
            display_label="Test User"
        )
        
        mock_db.get.side_effect = [mock_video, mock_user]
        
        # Test metadata creation
        from server.web.app.services.video_metadata_service import VideoMetadataInput
        
        metadata_input = VideoMetadataInput(
            title="Updated Title",
            description="Updated Description",
            tags=["updated", "test"]
        )
        
        result = await metadata_service.create_metadata(video_id, metadata_input, user_id)
        
        # Verify metadata updated
        assert mock_video.title == "Updated Title"
        assert mock_video.description == "Updated Description"
        assert mock_video.tags == ["updated", "test"]
        
        # Verify response
        assert result.title == "Updated Title"
        assert result.description == "Updated Description"
        assert result.tags == ["updated", "test"]
    
    async def test_streaming_and_analytics_integration(self, mock_db):
        """Test integration between streaming and analytics services."""
        
        # Setup streaming service
        streaming_service = StreamingService(mock_db)
        
        # Mock video and user
        video_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        
        mock_video = Video(
            id=video_id,
            creator_id=user_id,
            title="Test Video",
            status=VideoStatus.ready,
            duration_seconds=120
        )
        
        mock_db.get.return_value = mock_video
        
        # Create viewing session
        session = await streaming_service.create_viewing_session(
            video_id=video_id,
            user_id=user_id,
            ip_address="192.168.1.1"
        )
        
        # Mock session retrieval for progress updates
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        mock_db.execute.return_value = mock_result
        
        # Update progress multiple times (simulating viewing)
        progress_updates = [
            {'current_position_seconds': 30.0, 'completion_percentage': 25.0},
            {'current_position_seconds': 60.0, 'completion_percentage': 50.0},
            {'current_position_seconds': 90.0, 'completion_percentage': 75.0},
            {'current_position_seconds': 120.0, 'completion_percentage': 100.0}
        ]
        
        for progress in progress_updates:
            updated_session = await streaming_service.update_viewing_progress(
                session.session_token, video_id, progress
            )
            
            assert updated_session.current_position_seconds == progress['current_position_seconds']
            assert updated_session.completion_percentage == progress['completion_percentage']
        
        # End session
        final_data = {
            'current_position_seconds': 120.0,
            'completion_percentage': 100.0,
            'quality_switches': 2,
            'buffering_events': 1
        }
        
        ended_session = await streaming_service.end_viewing_session(
            session.session_token, video_id, final_data
        )
        
        assert ended_session.ended_at is not None
        assert ended_session.completion_percentage == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])