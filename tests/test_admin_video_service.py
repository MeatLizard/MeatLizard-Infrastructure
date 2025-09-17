"""
Tests for admin video service.
"""
import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.services.admin_video_service import AdminVideoService
from server.web.app.models import (
    User, Video, TranscodingJob, ViewSession, VideoComment, VideoLike,
    VideoStatus, TranscodingStatus, VideoVisibility
)


@pytest.fixture
async def admin_service():
    return AdminVideoService()


@pytest.fixture
async def sample_user(db_session: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        display_label="Test Creator",
        email="creator@example.com"
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def sample_video(db_session: AsyncSession, sample_user: User):
    video = Video(
        id=uuid.uuid4(),
        creator_id=sample_user.id,
        title="Test Video",
        description="Test video description",
        original_filename="test.mp4",
        original_s3_key="videos/test.mp4",
        file_size=1024 * 1024 * 100,  # 100MB
        duration_seconds=300,  # 5 minutes
        source_resolution="1920x1080",
        source_framerate=30,
        status=VideoStatus.ready,
        visibility=VideoVisibility.public
    )
    db_session.add(video)
    await db_session.commit()
    return video


@pytest.fixture
async def sample_transcoding_job(db_session: AsyncSession, sample_video: Video):
    job = TranscodingJob(
        id=uuid.uuid4(),
        video_id=sample_video.id,
        quality_preset="720p_30fps",
        target_resolution="1280x720",
        target_framerate=30,
        target_bitrate=2000000,
        status=TranscodingStatus.completed,
        progress_percent=100,
        output_s3_key="transcoded/test_720p.mp4",
        output_file_size=1024 * 1024 * 50  # 50MB
    )
    db_session.add(job)
    await db_session.commit()
    return job


class TestAdminVideoService:
    
    async def test_get_video_dashboard_stats(
        self, 
        admin_service: AdminVideoService, 
        db_session: AsyncSession,
        sample_video: Video,
        sample_transcoding_job: TranscodingJob
    ):
        """Test getting dashboard statistics."""
        stats = await admin_service.get_video_dashboard_stats(db_session)
        
        assert 'video_stats' in stats
        assert 'transcoding_stats' in stats
        assert 'storage' in stats
        assert 'recent_activity' in stats
        
        # Check video stats
        assert stats['video_stats']['ready'] >= 1
        
        # Check transcoding stats
        assert stats['transcoding_stats']['completed'] >= 1
        
        # Check storage info
        assert stats['storage']['total_videos'] >= 1
        assert stats['storage']['total_original_gb'] > 0
        assert stats['storage']['total_transcoded_gb'] > 0
    
    async def test_get_videos_list(
        self, 
        admin_service: AdminVideoService, 
        db_session: AsyncSession,
        sample_video: Video
    ):
        """Test getting paginated videos list."""
        result = await admin_service.get_videos_list(db_session)
        
        assert 'videos' in result
        assert 'pagination' in result
        
        # Check pagination info
        pagination = result['pagination']
        assert pagination['page'] == 1
        assert pagination['per_page'] == 50
        assert pagination['total_count'] >= 1
        
        # Check video data
        videos = result['videos']
        assert len(videos) >= 1
        
        video_data = videos[0]
        assert 'id' in video_data
        assert 'title' in video_data
        assert 'creator' in video_data
        assert 'status' in video_data
        assert 'visibility' in video_data
        assert 'transcoding_summary' in video_data
    
    async def test_get_videos_list_with_filters(
        self, 
        admin_service: AdminVideoService, 
        db_session: AsyncSession,
        sample_video: Video
    ):
        """Test getting videos list with filters."""
        # Test status filter
        result = await admin_service.get_videos_list(
            db_session,
            status_filter=VideoStatus.ready
        )
        
        assert len(result['videos']) >= 1
        for video in result['videos']:
            assert video['status'] == 'ready'
        
        # Test visibility filter
        result = await admin_service.get_videos_list(
            db_session,
            visibility_filter=VideoVisibility.public
        )
        
        assert len(result['videos']) >= 1
        for video in result['videos']:
            assert video['visibility'] == 'public'
        
        # Test search query
        result = await admin_service.get_videos_list(
            db_session,
            search_query="Test Video"
        )
        
        assert len(result['videos']) >= 1
    
    async def test_get_video_details(
        self, 
        admin_service: AdminVideoService, 
        db_session: AsyncSession,
        sample_video: Video,
        sample_transcoding_job: TranscodingJob
    ):
        """Test getting detailed video information."""
        details = await admin_service.get_video_details(db_session, sample_video.id)
        
        assert details is not None
        assert details['id'] == str(sample_video.id)
        assert details['title'] == sample_video.title
        assert 'creator' in details
        assert 'file_info' in details
        assert 'statistics' in details
        assert 'transcoding_jobs' in details
        
        # Check transcoding jobs
        transcoding_jobs = details['transcoding_jobs']
        assert len(transcoding_jobs) >= 1
        
        job_data = transcoding_jobs[0]
        assert job_data['quality_preset'] == "720p_30fps"
        assert job_data['status'] == "completed"
    
    async def test_get_video_details_not_found(
        self, 
        admin_service: AdminVideoService, 
        db_session: AsyncSession
    ):
        """Test getting details for non-existent video."""
        non_existent_id = uuid.uuid4()
        details = await admin_service.get_video_details(db_session, non_existent_id)
        
        assert details is None
    
    async def test_retry_failed_transcoding_job(
        self, 
        admin_service: AdminVideoService, 
        db_session: AsyncSession,
        sample_video: Video
    ):
        """Test retrying a failed transcoding job."""
        # Create a failed job
        failed_job = TranscodingJob(
            id=uuid.uuid4(),
            video_id=sample_video.id,
            quality_preset="1080p_30fps",
            target_resolution="1920x1080",
            target_framerate=30,
            target_bitrate=4000000,
            status=TranscodingStatus.failed,
            error_message="Test error"
        )
        db_session.add(failed_job)
        await db_session.commit()
        
        # Retry the job
        success = await admin_service.retry_failed_transcoding_job(db_session, failed_job.id)
        
        assert success is True
        
        # Verify job status was reset
        await db_session.refresh(failed_job)
        assert failed_job.status == TranscodingStatus.queued
        assert failed_job.progress_percent == 0
        assert failed_job.error_message is None
    
    async def test_retry_non_failed_job(
        self, 
        admin_service: AdminVideoService, 
        db_session: AsyncSession,
        sample_transcoding_job: TranscodingJob
    ):
        """Test retrying a non-failed job should fail."""
        success = await admin_service.retry_failed_transcoding_job(
            db_session, 
            sample_transcoding_job.id
        )
        
        assert success is False
    
    async def test_bulk_update_video_visibility(
        self, 
        admin_service: AdminVideoService, 
        db_session: AsyncSession,
        sample_video: Video
    ):
        """Test bulk updating video visibility."""
        video_ids = [sample_video.id]
        new_visibility = VideoVisibility.private
        
        updated_count = await admin_service.bulk_update_video_visibility(
            db_session, 
            video_ids, 
            new_visibility
        )
        
        assert updated_count == 1
        
        # Verify the video was updated
        await db_session.refresh(sample_video)
        assert sample_video.visibility == VideoVisibility.private
    
    async def test_bulk_delete_videos(
        self, 
        admin_service: AdminVideoService, 
        db_session: AsyncSession,
        sample_video: Video
    ):
        """Test bulk deleting videos."""
        video_ids = [sample_video.id]
        
        deleted_count = await admin_service.bulk_delete_videos(db_session, video_ids)
        
        assert deleted_count == 1
        
        # Verify the video was marked as deleted
        await db_session.refresh(sample_video)
        assert sample_video.status == VideoStatus.deleted
    
    async def test_get_storage_usage_report(
        self, 
        admin_service: AdminVideoService, 
        db_session: AsyncSession,
        sample_video: Video,
        sample_transcoding_job: TranscodingJob
    ):
        """Test getting storage usage report."""
        report = await admin_service.get_storage_usage_report(db_session)
        
        assert 'storage_by_status' in report
        assert 'storage_by_creator' in report
        assert 'storage_by_quality' in report
        
        # Check storage by status
        status_storage = report['storage_by_status']
        assert len(status_storage) > 0
        
        ready_storage = next((item for item in status_storage if item['status'] == 'ready'), None)
        assert ready_storage is not None
        assert ready_storage['video_count'] >= 1
        assert ready_storage['size_gb'] > 0
        
        # Check storage by creator
        creator_storage = report['storage_by_creator']
        assert len(creator_storage) >= 1
        
        # Check storage by quality
        quality_storage = report['storage_by_quality']
        assert len(quality_storage) >= 1
        
        quality_item = quality_storage[0]
        assert quality_item['quality_preset'] == "720p_30fps"
        assert quality_item['job_count'] >= 1
    
    async def test_get_transcoding_queue_status(
        self, 
        admin_service: AdminVideoService, 
        db_session: AsyncSession,
        sample_transcoding_job: TranscodingJob
    ):
        """Test getting transcoding queue status."""
        status = await admin_service.get_transcoding_queue_status(db_session)
        
        assert 'queue_status' in status
        assert 'recent_performance' in status
        assert 'common_errors' in status
        
        # Check queue status
        queue_status = status['queue_status']
        assert 'completed' in queue_status
        assert queue_status['completed'] >= 1
        
        # Check recent performance
        performance = status['recent_performance']
        assert 'completed_24h' in performance
        assert 'avg_duration_minutes' in performance