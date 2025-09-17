"""
Mock implementations for external dependencies in video services testing.
"""

from .mock_s3_service import (
    MockVideoS3Service,
    MockS3UploadSession,
    MockS3UploadResult,
    MockHLSService,
    create_mock_s3_service,
    create_mock_hls_service
)

from .mock_ffmpeg_service import (
    MockFFmpegService,
    MockFFprobeService,
    MockFFmpegProcess,
    create_mock_ffmpeg_service,
    create_mock_ffprobe_service,
    create_sample_video_analysis,
    create_sample_ffprobe_output,
    create_test_video_formats
)

__all__ = [
    # S3 Service Mocks
    'MockVideoS3Service',
    'MockS3UploadSession', 
    'MockS3UploadResult',
    'MockHLSService',
    'create_mock_s3_service',
    'create_mock_hls_service',
    
    # FFmpeg Service Mocks
    'MockFFmpegService',
    'MockFFprobeService',
    'MockFFmpegProcess',
    'create_mock_ffmpeg_service',
    'create_mock_ffprobe_service',
    
    # Test Data Utilities
    'create_sample_video_analysis',
    'create_sample_ffprobe_output',
    'create_test_video_formats'
]