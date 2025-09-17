"""
Mock implementations for S3 service for testing.
"""
import asyncio
import uuid
from typing import Dict, List, Optional, Any
from unittest.mock import MagicMock, AsyncMock


class MockS3UploadSession:
    """Mock S3 upload session for testing."""
    
    def __init__(self, upload_id: str, bucket: str, key: str):
        self.upload_id = upload_id
        self.bucket = bucket
        self.key = key
        self.parts = {}
        self.completed = False
        self.aborted = False
    
    def add_part(self, part_number: int, data: bytes) -> str:
        """Add a part to the upload session."""
        etag = f"etag-{part_number}-{len(data)}"
        self.parts[part_number] = {
            'etag': etag,
            'size': len(data),
            'data': data
        }
        return etag


class MockS3UploadResult:
    """Mock S3 upload result."""
    
    def __init__(self, success: bool, error_message: str = None):
        self.success = success
        self.error_message = error_message


class MockVideoS3Service:
    """Mock implementation of VideoS3Service for testing."""
    
    def __init__(self, bucket_name: str = "test-bucket", available: bool = True):
        self.bucket_name = bucket_name
        self._available = available
        self.upload_sessions: Dict[str, MockS3UploadSession] = {}
        self.stored_files: Dict[str, bytes] = {}
        self.upload_failure_rate = 0.0  # 0.0 = no failures, 1.0 = all failures
        self.download_failure_rate = 0.0
        
        # Statistics for testing
        self.upload_count = 0
        self.download_count = 0
        self.delete_count = 0
    
    def is_available(self) -> bool:
        """Check if S3 service is available."""
        return self._available
    
    def set_available(self, available: bool):
        """Set S3 service availability for testing."""
        self._available = available
    
    def set_upload_failure_rate(self, rate: float):
        """Set upload failure rate for testing (0.0 to 1.0)."""
        self.upload_failure_rate = max(0.0, min(1.0, rate))
    
    def set_download_failure_rate(self, rate: float):
        """Set download failure rate for testing (0.0 to 1.0)."""
        self.download_failure_rate = max(0.0, min(1.0, rate))
    
    def generate_video_key(self, video_id: str, filename: str) -> str:
        """Generate S3 key for video file."""
        extension = filename.split('.')[-1] if '.' in filename else 'mp4'
        return f"videos/{video_id}/original.{extension}"
    
    async def initiate_multipart_upload(self, video_id: str, filename: str, content_type: str) -> MockS3UploadSession:
        """Initiate multipart upload."""
        if not self._available:
            raise Exception("S3 service not available")
        
        # Simulate failure rate
        import random
        if random.random() < self.upload_failure_rate:
            raise Exception("Simulated S3 upload initiation failure")
        
        upload_id = str(uuid.uuid4())
        key = self.generate_video_key(video_id, filename)
        
        session = MockS3UploadSession(upload_id, self.bucket_name, key)
        self.upload_sessions[upload_id] = session
        
        # Simulate network delay
        await asyncio.sleep(0.01)
        
        return session
    
    async def upload_part(self, session: MockS3UploadSession, part_number: int, data: bytes) -> str:
        """Upload a part of multipart upload."""
        if not self._available:
            raise Exception("S3 service not available")
        
        if session.aborted:
            raise Exception("Upload session has been aborted")
        
        if session.completed:
            raise Exception("Upload session has been completed")
        
        # Simulate failure rate
        import random
        if random.random() < self.upload_failure_rate:
            raise Exception("Simulated S3 part upload failure")
        
        # Simulate network delay based on data size
        delay = len(data) / (1024 * 1024 * 100)  # Simulate 100 MB/s
        await asyncio.sleep(min(delay, 0.1))  # Cap at 100ms
        
        etag = session.add_part(part_number, data)
        self.upload_count += 1
        
        return etag
    
    async def complete_multipart_upload(self, session: MockS3UploadSession) -> MockS3UploadResult:
        """Complete multipart upload."""
        if not self._available:
            return MockS3UploadResult(False, "S3 service not available")
        
        if session.aborted:
            return MockS3UploadResult(False, "Upload session has been aborted")
        
        if session.completed:
            return MockS3UploadResult(False, "Upload session already completed")
        
        # Simulate failure rate
        import random
        if random.random() < self.upload_failure_rate:
            return MockS3UploadResult(False, "Simulated S3 upload completion failure")
        
        # Combine all parts into final file
        combined_data = b""
        for part_num in sorted(session.parts.keys()):
            combined_data += session.parts[part_num]['data']
        
        self.stored_files[session.key] = combined_data
        session.completed = True
        
        # Simulate network delay
        await asyncio.sleep(0.02)
        
        return MockS3UploadResult(True)
    
    async def abort_multipart_upload(self, session: MockS3UploadSession):
        """Abort multipart upload."""
        session.aborted = True
        
        # Clean up session
        if session.upload_id in self.upload_sessions:
            del self.upload_sessions[session.upload_id]
        
        # Simulate network delay
        await asyncio.sleep(0.01)
    
    async def upload_file_content(self, content: bytes, key: str, content_type: str = None):
        """Upload file content directly."""
        if not self._available:
            raise Exception("S3 service not available")
        
        # Simulate failure rate
        import random
        if random.random() < self.upload_failure_rate:
            raise Exception("Simulated S3 file upload failure")
        
        # Simulate network delay
        delay = len(content) / (1024 * 1024 * 50)  # Simulate 50 MB/s
        await asyncio.sleep(min(delay, 0.2))  # Cap at 200ms
        
        self.stored_files[key] = content
        self.upload_count += 1
    
    async def download_file(self, key: str, local_path: str):
        """Download file from S3 to local path."""
        if not self._available:
            raise Exception("S3 service not available")
        
        # Simulate failure rate
        import random
        if random.random() < self.download_failure_rate:
            raise Exception("Simulated S3 download failure")
        
        if key not in self.stored_files:
            raise Exception(f"File not found: {key}")
        
        # Simulate network delay
        file_size = len(self.stored_files[key])
        delay = file_size / (1024 * 1024 * 100)  # Simulate 100 MB/s
        await asyncio.sleep(min(delay, 0.5))  # Cap at 500ms
        
        # In real implementation, would write to local_path
        # For testing, we just track the download
        self.download_count += 1
    
    async def get_file_content(self, key: str) -> bytes:
        """Get file content from S3."""
        if not self._available:
            raise Exception("S3 service not available")
        
        # Simulate failure rate
        import random
        if random.random() < self.download_failure_rate:
            raise Exception("Simulated S3 get content failure")
        
        if key not in self.stored_files:
            raise Exception(f"File not found: {key}")
        
        # Simulate network delay
        file_size = len(self.stored_files[key])
        delay = file_size / (1024 * 1024 * 100)  # Simulate 100 MB/s
        await asyncio.sleep(min(delay, 0.1))  # Cap at 100ms
        
        self.download_count += 1
        return self.stored_files[key]
    
    async def get_file_url(self, key: str, expires_in: int = 3600) -> str:
        """Get presigned URL for file."""
        if not self._available:
            raise Exception("S3 service not available")
        
        if key not in self.stored_files:
            raise Exception(f"File not found: {key}")
        
        # Return mock URL
        return f"https://mock-s3.amazonaws.com/{self.bucket_name}/{key}?expires={expires_in}"
    
    async def delete_file(self, key: str):
        """Delete file from S3."""
        if not self._available:
            raise Exception("S3 service not available")
        
        if key in self.stored_files:
            del self.stored_files[key]
            self.delete_count += 1
        
        # Simulate network delay
        await asyncio.sleep(0.01)
    
    async def delete_folder(self, prefix: str):
        """Delete all files with given prefix."""
        if not self._available:
            raise Exception("S3 service not available")
        
        keys_to_delete = [key for key in self.stored_files.keys() if key.startswith(prefix)]
        
        for key in keys_to_delete:
            del self.stored_files[key]
            self.delete_count += 1
        
        # Simulate network delay
        await asyncio.sleep(0.02)
    
    def list_files(self, prefix: str = "") -> List[str]:
        """List files with given prefix."""
        return [key for key in self.stored_files.keys() if key.startswith(prefix)]
    
    def get_file_size(self, key: str) -> int:
        """Get file size."""
        if key not in self.stored_files:
            raise Exception(f"File not found: {key}")
        
        return len(self.stored_files[key])
    
    def file_exists(self, key: str) -> bool:
        """Check if file exists."""
        return key in self.stored_files
    
    def clear_all_files(self):
        """Clear all stored files (for testing)."""
        self.stored_files.clear()
        self.upload_sessions.clear()
        self.upload_count = 0
        self.download_count = 0
        self.delete_count = 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics for testing."""
        return {
            'upload_count': self.upload_count,
            'download_count': self.download_count,
            'delete_count': self.delete_count,
            'stored_files_count': len(self.stored_files),
            'active_upload_sessions': len(self.upload_sessions),
            'total_stored_size': sum(len(data) for data in self.stored_files.values())
        }


class MockHLSService:
    """Mock implementation of HLS service for testing."""
    
    def __init__(self, bucket_name: str = "test-bucket"):
        self.bucket_name = bucket_name
        self.available_qualities: Dict[str, List[Dict]] = {}
        self.streaming_urls: Dict[str, str] = {}
    
    def set_available_qualities(self, video_id: str, qualities: List[Dict]):
        """Set available qualities for a video."""
        self.available_qualities[video_id] = qualities
    
    async def get_available_qualities(self, video_id: str) -> List[Dict]:
        """Get available qualities for a video."""
        return self.available_qualities.get(video_id, [])
    
    def get_streaming_url(self, video_id: str, quality: str = None) -> str:
        """Get streaming URL for video."""
        if quality:
            return f"https://mock-cdn.example.com/video/{video_id}/{quality}/playlist.m3u8"
        else:
            return f"https://mock-cdn.example.com/video/{video_id}/master.m3u8"
    
    async def generate_hls_manifest(self, video_id: str, qualities: List[str]) -> str:
        """Generate HLS master manifest."""
        manifest_lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
        
        for quality in qualities:
            manifest_lines.append(f"#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080")
            manifest_lines.append(f"{quality}/playlist.m3u8")
        
        return "\n".join(manifest_lines)
    
    async def create_quality_playlist(self, video_id: str, quality: str, segment_duration: float = 6.0) -> str:
        """Create quality-specific playlist."""
        playlist_lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            f"#EXT-X-TARGETDURATION:{int(segment_duration)}",
            "#EXT-X-MEDIA-SEQUENCE:0"
        ]
        
        # Mock segments
        for i in range(10):  # 10 segments
            playlist_lines.append(f"#EXTINF:{segment_duration:.1f},")
            playlist_lines.append(f"segment_{i:03d}.ts")
        
        playlist_lines.append("#EXT-X-ENDLIST")
        
        return "\n".join(playlist_lines)


def create_mock_s3_service(**kwargs) -> MockVideoS3Service:
    """Factory function to create mock S3 service."""
    return MockVideoS3Service(**kwargs)


def create_mock_hls_service(**kwargs) -> MockHLSService:
    """Factory function to create mock HLS service."""
    return MockHLSService(**kwargs)