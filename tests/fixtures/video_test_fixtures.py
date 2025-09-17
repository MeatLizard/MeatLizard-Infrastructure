"""
Test fixtures for various video formats and scenarios.
"""
import pytest
import uuid
import tempfile
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any

from server.web.app.models import Video, VideoStatus, VideoVisibility, User, ViewSession, TranscodingJob, TranscodingStatus
from server.web.app.services.video_upload_service import VideoMetadata, UploadSession
from server.web.app.services.video_analysis_service import VideoAnalysis
from server.web.app.services.thumbnail_service import ThumbnailInfo


@pytest.fixture
def sample_users():
    """Create sample users for testing."""
    return [
        User(
            id=str(uuid.uuid4()),
            display_label="Test Creator 1",
            email="creator1@example.com"
        ),
        User(
            id=str(uuid.uuid4()),
            display_label="Test Creator 2", 
            email="creator2@example.com"
        ),
        User(
            id=str(uuid.uuid4()),
            display_label="Test Viewer",
            email="viewer@example.com"
        )
    ]


@pytest.fixture
def sample_videos(sample_users):
    """Create sample videos with different properties."""
    creator1, creator2, viewer = sample_users
    
    return [
        # Public 1080p video
        Video(
            id=str(uuid.uuid4()),
            creator_id=creator1.id,
            title="Public 1080p Test Video",
            description="A public test video in 1080p resolution",
            tags=["test", "public", "1080p"],
            original_filename="test_1080p.mp4",
            original_s3_key="videos/test1/original.mp4",
            file_size=100 * 1024 * 1024,  # 100MB
            duration_seconds=120,
            source_resolution="1920x1080",
            source_framerate=30,
            source_codec="h264",
            source_bitrate=5000000,
            status=VideoStatus.ready,
            visibility=VideoVisibility.public,
            thumbnail_s3_key="thumbnails/test1/thumb_02_60_0s.jpg",
            created_at=datetime.utcnow() - timedelta(days=1),
            updated_at=datetime.utcnow() - timedelta(hours=1)
        ),
        
        # Private 720p video
        Video(
            id=str(uuid.uuid4()),
            creator_id=creator1.id,
            title="Private 720p Test Video",
            description="A private test video in 720p resolution",
            tags=["test", "private", "720p"],
            original_filename="test_720p.mp4",
            original_s3_key="videos/test2/original.mp4",
            file_size=50 * 1024 * 1024,  # 50MB
            duration_seconds=180,
            source_resolution="1280x720",
            source_framerate=60,
            source_codec="h264",
            source_bitrate=3000000,
            status=VideoStatus.ready,
            visibility=VideoVisibility.private,
            thumbnail_s3_key="thumbnails/test2/thumb_01_45_0s.jpg",
            created_at=datetime.utcnow() - timedelta(hours=12),
            updated_at=datetime.utcnow() - timedelta(minutes=30)
        ),
        
        # Unlisted 4K video
        Video(
            id=str(uuid.uuid4()),
            creator_id=creator2.id,
            title="Unlisted 4K Test Video",
            description="An unlisted test video in 4K resolution",
            tags=["test", "unlisted", "4k", "high-quality"],
            original_filename="test_4k.mp4",
            original_s3_key="videos/test3/original.mp4",
            file_size=500 * 1024 * 1024,  # 500MB
            duration_seconds=300,
            source_resolution="3840x2160",
            source_framerate=30,
            source_codec="h265",
            source_bitrate=15000000,
            status=VideoStatus.ready,
            visibility=VideoVisibility.unlisted,
            thumbnail_s3_key="thumbnails/test3/thumb_03_150_0s.jpg",
            created_at=datetime.utcnow() - timedelta(hours=6),
            updated_at=datetime.utcnow() - timedelta(minutes=15)
        ),
        
        # Processing video
        Video(
            id=str(uuid.uuid4()),
            creator_id=creator2.id,
            title="Processing Test Video",
            description="A video currently being processed",
            tags=["test", "processing"],
            original_filename="test_processing.mp4",
            original_s3_key="videos/test4/original.mp4",
            file_size=75 * 1024 * 1024,  # 75MB
            duration_seconds=90,
            source_resolution="1920x1080",
            source_framerate=30,
            source_codec="h264",
            source_bitrate=4000000,
            status=VideoStatus.processing,
            visibility=VideoVisibility.public,
            created_at=datetime.utcnow() - timedelta(minutes=30),
            updated_at=datetime.utcnow() - timedelta(minutes=5)
        ),
        
        # Failed video
        Video(
            id=str(uuid.uuid4()),
            creator_id=creator1.id,
            title="Failed Test Video",
            description="A video that failed processing",
            tags=["test", "failed"],
            original_filename="test_failed.mp4",
            original_s3_key="videos/test5/original.mp4",
            file_size=25 * 1024 * 1024,  # 25MB
            duration_seconds=0,
            status=VideoStatus.failed,
            visibility=VideoVisibility.private,
            created_at=datetime.utcnow() - timedelta(hours=2),
            updated_at=datetime.utcnow() - timedelta(hours=1)
        )
    ]


@pytest.fixture
def sample_transcoding_jobs(sample_videos):
    """Create sample transcoding jobs."""
    video1, video2, video3, video4, video5 = sample_videos
    
    return [
        # Completed transcoding jobs for video1
        TranscodingJob(
            id=str(uuid.uuid4()),
            video_id=video1.id,
            quality_preset="720p_30fps",
            target_resolution="1280x720",
            target_framerate=30,
            target_bitrate=2500,
            status=TranscodingStatus.completed,
            progress_percent=100.0,
            output_s3_key="videos/test1/720p_30fps/video.mp4",
            hls_manifest_s3_key="videos/test1/720p_30fps/playlist.m3u8",
            output_file_size=40 * 1024 * 1024,
            started_at=datetime.utcnow() - timedelta(hours=2),
            completed_at=datetime.utcnow() - timedelta(hours=1, minutes=45),
            created_at=datetime.utcnow() - timedelta(hours=2, minutes=5)
        ),
        
        TranscodingJob(
            id=str(uuid.uuid4()),
            video_id=video1.id,
            quality_preset="1080p_30fps",
            target_resolution="1920x1080",
            target_framerate=30,
            target_bitrate=5000,
            status=TranscodingStatus.completed,
            progress_percent=100.0,
            output_s3_key="videos/test1/1080p_30fps/video.mp4",
            hls_manifest_s3_key="videos/test1/1080p_30fps/playlist.m3u8",
            output_file_size=80 * 1024 * 1024,
            started_at=datetime.utcnow() - timedelta(hours=1, minutes=50),
            completed_at=datetime.utcnow() - timedelta(hours=1, minutes=30),
            created_at=datetime.utcnow() - timedelta(hours=2)
        ),
        
        # Processing transcoding job for video4
        TranscodingJob(
            id=str(uuid.uuid4()),
            video_id=video4.id,
            quality_preset="720p_30fps",
            target_resolution="1280x720",
            target_framerate=30,
            target_bitrate=2500,
            status=TranscodingStatus.processing,
            progress_percent=65.0,
            started_at=datetime.utcnow() - timedelta(minutes=15),
            created_at=datetime.utcnow() - timedelta(minutes=20)
        ),
        
        # Failed transcoding job for video5
        TranscodingJob(
            id=str(uuid.uuid4()),
            video_id=video5.id,
            quality_preset="720p_30fps",
            target_resolution="1280x720",
            target_framerate=30,
            target_bitrate=2500,
            status=TranscodingStatus.failed,
            progress_percent=25.0,
            error_message="FFmpeg encoding error: Invalid input format",
            started_at=datetime.utcnow() - timedelta(hours=1, minutes=30),
            created_at=datetime.utcnow() - timedelta(hours=1, minutes=35)
        )
    ]


@pytest.fixture
def sample_view_sessions(sample_videos, sample_users):
    """Create sample viewing sessions."""
    video1, video2, video3, _, _ = sample_videos
    creator1, creator2, viewer = sample_users
    
    return [
        # Completed viewing session
        ViewSession(
            id=str(uuid.uuid4()),
            video_id=video1.id,
            user_id=viewer.id,
            session_token="session_token_1",
            ip_address_hash="hashed_ip_1",
            user_agent_hash="hashed_ua_1",
            current_position_seconds=120.0,
            total_watch_time_seconds=115.0,
            completion_percentage=100.0,
            qualities_used=["720p_30fps", "1080p_30fps"],
            quality_switches=2,
            buffering_events=1,
            started_at=datetime.utcnow() - timedelta(hours=3),
            last_heartbeat=datetime.utcnow() - timedelta(hours=2, minutes=58),
            ended_at=datetime.utcnow() - timedelta(hours=2, minutes=58)
        ),
        
        # Partial viewing session
        ViewSession(
            id=str(uuid.uuid4()),
            video_id=video1.id,
            user_id=creator2.id,
            session_token="session_token_2",
            ip_address_hash="hashed_ip_2",
            user_agent_hash="hashed_ua_2",
            current_position_seconds=75.0,
            total_watch_time_seconds=70.0,
            completion_percentage=62.5,
            qualities_used=["720p_30fps"],
            quality_switches=0,
            buffering_events=0,
            started_at=datetime.utcnow() - timedelta(hours=1),
            last_heartbeat=datetime.utcnow() - timedelta(minutes=30),
            ended_at=datetime.utcnow() - timedelta(minutes=30)
        ),
        
        # Active viewing session
        ViewSession(
            id=str(uuid.uuid4()),
            video_id=video3.id,
            user_id=viewer.id,
            session_token="session_token_3",
            ip_address_hash="hashed_ip_3",
            user_agent_hash="hashed_ua_3",
            current_position_seconds=150.0,
            total_watch_time_seconds=140.0,
            completion_percentage=50.0,
            qualities_used=["1080p_30fps", "1440p_30fps"],
            quality_switches=3,
            buffering_events=2,
            started_at=datetime.utcnow() - timedelta(minutes=10),
            last_heartbeat=datetime.utcnow() - timedelta(seconds=30)
        )
    ]


@pytest.fixture
def sample_video_metadata():
    """Create sample video metadata for testing."""
    return [
        VideoMetadata(
            title="Sample Video 1",
            description="A sample video for testing purposes",
            tags=["sample", "test", "video"]
        ),
        
        VideoMetadata(
            title="Educational Content",
            description="Educational video content with detailed explanations and examples",
            tags=["education", "tutorial", "learning", "howto"]
        ),
        
        VideoMetadata(
            title="Entertainment Video",
            description="Fun and entertaining video content for viewers",
            tags=["entertainment", "fun", "comedy", "viral"]
        ),
        
        VideoMetadata(
            title="Technical Demo",
            description="Technical demonstration of software features and capabilities",
            tags=["tech", "demo", "software", "features", "development"]
        )
    ]


@pytest.fixture
def sample_upload_sessions(sample_users):
    """Create sample upload sessions."""
    creator1, creator2, _ = sample_users
    
    return [
        UploadSession(
            session_id=str(uuid.uuid4()),
            video_id=str(uuid.uuid4()),
            user_id=creator1.id,
            metadata={
                'filename': 'test_upload_1.mp4',
                'size': 100 * 1024 * 1024,
                'total_chunks': 10,
                'mime_type': 'video/mp4'
            }
        ),
        
        UploadSession(
            session_id=str(uuid.uuid4()),
            video_id=str(uuid.uuid4()),
            user_id=creator2.id,
            metadata={
                'filename': 'test_upload_2.mov',
                'size': 250 * 1024 * 1024,
                'total_chunks': 25,
                'mime_type': 'video/quicktime'
            }
        )
    ]


@pytest.fixture
def sample_video_analyses():
    """Create sample video analysis results."""
    return [
        VideoAnalysis(
            duration_seconds=120.5,
            width=1920,
            height=1080,
            framerate=30.0,
            codec="h264",
            bitrate=5000000,
            format_name="mp4",
            file_size=100 * 1024 * 1024,
            is_valid=True
        ),
        
        VideoAnalysis(
            duration_seconds=180.0,
            width=1280,
            height=720,
            framerate=60.0,
            codec="h264",
            bitrate=3000000,
            format_name="mov",
            file_size=75 * 1024 * 1024,
            is_valid=True
        ),
        
        VideoAnalysis(
            duration_seconds=300.0,
            width=3840,
            height=2160,
            framerate=30.0,
            codec="h265",
            bitrate=15000000,
            format_name="mp4",
            file_size=500 * 1024 * 1024,
            is_valid=True
        ),
        
        # Invalid analysis result
        VideoAnalysis(
            duration_seconds=0,
            width=0,
            height=0,
            framerate=0,
            codec="",
            bitrate=0,
            format_name="",
            file_size=0,
            is_valid=False,
            error_message="Invalid video format"
        )
    ]


@pytest.fixture
def sample_thumbnail_infos(sample_videos):
    """Create sample thumbnail information."""
    video1, video2, video3, _, _ = sample_videos
    
    return [
        # Thumbnails for video1
        [
            ThumbnailInfo(
                timestamp=12.0,
                filename="thumb_00_12_0s.jpg",
                s3_key=f"thumbnails/{video1.id}/thumb_00_12_0s.jpg",
                local_path=f"/tmp/thumbnails/{video1.id}/thumb_00_12_0s.jpg",
                width=320,
                height=180,
                file_size=15000,
                is_selected=False
            ),
            ThumbnailInfo(
                timestamp=30.0,
                filename="thumb_01_30_0s.jpg",
                s3_key=f"thumbnails/{video1.id}/thumb_01_30_0s.jpg",
                local_path=f"/tmp/thumbnails/{video1.id}/thumb_01_30_0s.jpg",
                width=320,
                height=180,
                file_size=16000,
                is_selected=False
            ),
            ThumbnailInfo(
                timestamp=60.0,
                filename="thumb_02_60_0s.jpg",
                s3_key=f"thumbnails/{video1.id}/thumb_02_60_0s.jpg",
                local_path=f"/tmp/thumbnails/{video1.id}/thumb_02_60_0s.jpg",
                width=320,
                height=180,
                file_size=17000,
                is_selected=True  # Selected thumbnail
            ),
            ThumbnailInfo(
                timestamp=90.0,
                filename="thumb_03_90_0s.jpg",
                s3_key=f"thumbnails/{video1.id}/thumb_03_90_0s.jpg",
                local_path=f"/tmp/thumbnails/{video1.id}/thumb_03_90_0s.jpg",
                width=320,
                height=180,
                file_size=15500,
                is_selected=False
            ),
            ThumbnailInfo(
                timestamp=108.0,
                filename="thumb_04_108_0s.jpg",
                s3_key=f"thumbnails/{video1.id}/thumb_04_108_0s.jpg",
                local_path=f"/tmp/thumbnails/{video1.id}/thumb_04_108_0s.jpg",
                width=320,
                height=180,
                file_size=16500,
                is_selected=False
            )
        ]
    ]


@pytest.fixture
def sample_quality_presets():
    """Create sample quality presets for testing."""
    return [
        {
            "name": "480p_30fps",
            "resolution": "854x480",
            "width": 854,
            "height": 480,
            "framerate": 30,
            "bitrate": 1000,
            "description": "Standard definition 30fps"
        },
        {
            "name": "720p_30fps", 
            "resolution": "1280x720",
            "width": 1280,
            "height": 720,
            "framerate": 30,
            "bitrate": 2500,
            "description": "High definition 30fps"
        },
        {
            "name": "720p_60fps",
            "resolution": "1280x720", 
            "width": 1280,
            "height": 720,
            "framerate": 60,
            "bitrate": 3500,
            "description": "High definition 60fps"
        },
        {
            "name": "1080p_30fps",
            "resolution": "1920x1080",
            "width": 1920,
            "height": 1080,
            "framerate": 30,
            "bitrate": 5000,
            "description": "Full HD 30fps"
        },
        {
            "name": "1080p_60fps",
            "resolution": "1920x1080",
            "width": 1920,
            "height": 1080,
            "framerate": 60,
            "bitrate": 7000,
            "description": "Full HD 60fps"
        },
        {
            "name": "1440p_30fps",
            "resolution": "2560x1440",
            "width": 2560,
            "height": 1440,
            "framerate": 30,
            "bitrate": 8000,
            "description": "Quad HD 30fps"
        },
        {
            "name": "1440p_60fps",
            "resolution": "2560x1440",
            "width": 2560,
            "height": 1440,
            "framerate": 60,
            "bitrate": 12000,
            "description": "Quad HD 60fps"
        }
    ]


@pytest.fixture
def temp_video_files():
    """Create temporary video files for testing."""
    temp_files = []
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    
    # Create mock video files
    video_files = [
        ("test_1080p.mp4", b"mock 1080p video data" * 1000),
        ("test_720p.mov", b"mock 720p video data" * 500),
        ("test_4k.mp4", b"mock 4k video data" * 2000),
        ("test_invalid.txt", b"not a video file"),
        ("test_corrupted.mp4", b"corrupted video data")
    ]
    
    for filename, content in video_files:
        file_path = os.path.join(temp_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(content)
        temp_files.append(file_path)
    
    yield temp_files
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_file_info():
    """Create sample file information for testing."""
    return [
        {
            'filename': 'test_video_1.mp4',
            'size': 100 * 1024 * 1024,  # 100MB
            'total_chunks': 10,
            'mime_type': 'video/mp4'
        },
        {
            'filename': 'test_video_2.mov',
            'size': 250 * 1024 * 1024,  # 250MB
            'total_chunks': 25,
            'mime_type': 'video/quicktime'
        },
        {
            'filename': 'test_video_3.avi',
            'size': 500 * 1024 * 1024,  # 500MB
            'total_chunks': 50,
            'mime_type': 'video/x-msvideo'
        },
        {
            'filename': 'test_large_video.mkv',
            'size': 2 * 1024 * 1024 * 1024,  # 2GB
            'total_chunks': 200,
            'mime_type': 'video/x-matroska'
        }
    ]


def create_test_scenario(scenario_name: str) -> Dict[str, Any]:
    """Create test scenarios for different use cases."""
    scenarios = {
        "basic_upload": {
            "description": "Basic video upload scenario",
            "video_count": 1,
            "user_count": 1,
            "file_size": 100 * 1024 * 1024,
            "duration": 120,
            "quality_presets": ["720p_30fps", "1080p_30fps"]
        },
        
        "high_volume": {
            "description": "High volume upload scenario",
            "video_count": 50,
            "user_count": 10,
            "file_size": 50 * 1024 * 1024,
            "duration": 60,
            "quality_presets": ["480p_30fps", "720p_30fps"]
        },
        
        "large_file": {
            "description": "Large file upload scenario",
            "video_count": 1,
            "user_count": 1,
            "file_size": 5 * 1024 * 1024 * 1024,  # 5GB
            "duration": 3600,  # 1 hour
            "quality_presets": ["720p_30fps", "1080p_30fps", "1440p_30fps"]
        },
        
        "concurrent_streaming": {
            "description": "Concurrent streaming scenario",
            "video_count": 10,
            "user_count": 100,
            "concurrent_sessions": 50,
            "quality_presets": ["480p_30fps", "720p_30fps", "1080p_30fps"]
        },
        
        "transcoding_stress": {
            "description": "Transcoding stress test scenario",
            "video_count": 20,
            "concurrent_jobs": 10,
            "quality_presets": ["480p_30fps", "720p_30fps", "1080p_30fps", "1440p_30fps"]
        }
    }
    
    return scenarios.get(scenario_name, scenarios["basic_upload"])