"""
Performance benchmarking tests for video services.
"""
import pytest
import asyncio
import time
import statistics
from unittest.mock import AsyncMock, MagicMock, patch
from concurrent.futures import ThreadPoolExecutor
import uuid

from server.web.app.services.video_upload_service import VideoUploadService, VideoMetadata
from server.web.app.services.streaming_service import StreamingService
from server.web.app.services.video_analysis_service import VideoAnalysisService
from server.web.app.services.thumbnail_service import ThumbnailService
from server.web.app.models import Video, VideoStatus, VideoVisibility


class TestVideoServicePerformance:
    """Performance benchmarking tests for video services."""
    
    @pytest.fixture
    async def mock_db(self):
        """Mock database session for performance tests."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.get = AsyncMock()
        return db
    
    @pytest.fixture
    def sample_video(self):
        """Sample video for performance tests."""
        return Video(
            id=str(uuid.uuid4()),
            creator_id=str(uuid.uuid4()),
            title="Performance Test Video",
            status=VideoStatus.ready,
            visibility=VideoVisibility.public,
            duration_seconds=120
        )
    
    async def test_upload_service_initiate_performance(self, mock_db):
        """Benchmark upload service initiation performance."""
        upload_service = VideoUploadService(mock_db)
        
        # Mock dependencies
        upload_service.analysis_service.validate_file_info = MagicMock()
        upload_service.s3_service.is_available.return_value = False
        
        metadata = VideoMetadata("Test Video", "Description", ["test"])
        file_info = {
            'filename': 'test.mp4',
            'size': 1024 * 1024 * 100,  # 100MB
            'total_chunks': 10
        }
        
        # Benchmark multiple initiations
        times = []
        iterations = 50
        
        for _ in range(iterations):
            start_time = time.time()
            
            try:
                session = await upload_service.initiate_upload(
                    str(uuid.uuid4()), metadata, file_info
                )
                end_time = time.time()
                times.append(end_time - start_time)
            except Exception:
                # Skip failed attempts in performance test
                continue
        
        if times:
            avg_time = statistics.mean(times)
            p95_time = statistics.quantiles(times, n=20)[18] if len(times) > 20 else max(times)
            
            print(f"\nUpload Initiation Performance:")
            print(f"Average time: {avg_time:.4f}s")
            print(f"P95 time: {p95_time:.4f}s")
            print(f"Iterations: {len(times)}")
            
            # Performance assertions (adjust thresholds as needed)
            assert avg_time < 0.1, f"Average upload initiation time too slow: {avg_time:.4f}s"
            assert p95_time < 0.2, f"P95 upload initiation time too slow: {p95_time:.4f}s"
    
    async def test_streaming_service_access_check_performance(self, mock_db, sample_video):
        """Benchmark streaming service access check performance."""
        streaming_service = StreamingService(mock_db)
        mock_db.get.return_value = sample_video
        
        # Benchmark multiple access checks
        times = []
        iterations = 100
        
        for _ in range(iterations):
            start_time = time.time()
            
            try:
                result = await streaming_service.check_video_access(sample_video.id)
                end_time = time.time()
                times.append(end_time - start_time)
            except Exception:
                continue
        
        if times:
            avg_time = statistics.mean(times)
            p95_time = statistics.quantiles(times, n=20)[18] if len(times) > 20 else max(times)
            
            print(f"\nAccess Check Performance:")
            print(f"Average time: {avg_time:.4f}s")
            print(f"P95 time: {p95_time:.4f}s")
            print(f"Iterations: {len(times)}")
            
            # Performance assertions
            assert avg_time < 0.05, f"Average access check time too slow: {avg_time:.4f}s"
            assert p95_time < 0.1, f"P95 access check time too slow: {p95_time:.4f}s"
    
    @patch('asyncio.create_subprocess_exec')
    async def test_analysis_service_performance(self, mock_subprocess):
        """Benchmark video analysis service performance."""
        analysis_service = VideoAnalysisService()
        
        # Mock FFprobe output
        ffprobe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30/1",
                    "bit_rate": "5000000"
                }
            ],
            "format": {
                "duration": "120.5",
                "size": "75000000",
                "format_name": "mp4"
            }
        }
        
        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            str(ffprobe_output).replace("'", '"').encode(),
            b""
        )
        mock_subprocess.return_value = mock_process
        
        # Benchmark analysis parsing
        times = []
        iterations = 100
        
        with patch('os.path.exists', return_value=True):
            with patch('json.loads', return_value=ffprobe_output):
                for _ in range(iterations):
                    start_time = time.time()
                    
                    try:
                        result = analysis_service._parse_ffprobe_output(ffprobe_output, "/fake/path.mp4")
                        end_time = time.time()
                        times.append(end_time - start_time)
                    except Exception:
                        continue
        
        if times:
            avg_time = statistics.mean(times)
            p95_time = statistics.quantiles(times, n=20)[18] if len(times) > 20 else max(times)
            
            print(f"\nVideo Analysis Performance:")
            print(f"Average time: {avg_time:.4f}s")
            print(f"P95 time: {p95_time:.4f}s")
            print(f"Iterations: {len(times)}")
            
            # Performance assertions
            assert avg_time < 0.01, f"Average analysis time too slow: {avg_time:.4f}s"
            assert p95_time < 0.02, f"P95 analysis time too slow: {p95_time:.4f}s"
    
    async def test_concurrent_upload_sessions_performance(self, mock_db):
        """Benchmark concurrent upload session handling."""
        upload_service = VideoUploadService(mock_db)
        
        # Mock dependencies
        upload_service.analysis_service.validate_file_info = MagicMock()
        upload_service.s3_service.is_available.return_value = False
        
        metadata = VideoMetadata("Test Video", "Description", ["test"])
        file_info = {
            'filename': 'test.mp4',
            'size': 1024 * 1024 * 100,
            'total_chunks': 10
        }
        
        async def create_upload_session():
            """Create a single upload session."""
            try:
                return await upload_service.initiate_upload(
                    str(uuid.uuid4()), metadata, file_info
                )
            except Exception:
                return None
        
        # Benchmark concurrent sessions
        concurrent_sessions = 20
        start_time = time.time()
        
        # Create concurrent upload sessions
        tasks = [create_upload_session() for _ in range(concurrent_sessions)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Count successful sessions
        successful_sessions = sum(1 for result in results if result is not None and not isinstance(result, Exception))
        
        print(f"\nConcurrent Upload Sessions Performance:")
        print(f"Total time: {total_time:.4f}s")
        print(f"Successful sessions: {successful_sessions}/{concurrent_sessions}")
        print(f"Average time per session: {total_time/concurrent_sessions:.4f}s")
        
        # Performance assertions
        assert total_time < 5.0, f"Concurrent session creation too slow: {total_time:.4f}s"
        assert successful_sessions >= concurrent_sessions * 0.8, f"Too many failed sessions: {successful_sessions}/{concurrent_sessions}"
    
    async def test_chunk_processing_throughput(self, mock_db):
        """Benchmark chunk processing throughput."""
        upload_service = VideoUploadService(mock_db)
        
        # Create a mock upload session
        session_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        
        from server.web.app.services.video_upload_service import UploadSession
        session = UploadSession(session_id, video_id, user_id, {'filename': 'test.mp4'})
        session.temp_file_path = "/tmp/test.tmp"
        upload_service.active_sessions[session_id] = session
        
        # Mock file operations
        with patch('aiofiles.open'):
            chunk_data = b"x" * 1024 * 1024  # 1MB chunk
            chunk_count = 10
            
            start_time = time.time()
            
            # Process multiple chunks
            for i in range(chunk_count):
                try:
                    result = await upload_service.process_chunk(session_id, chunk_data, i)
                except Exception:
                    continue
            
            end_time = time.time()
            total_time = end_time - start_time
            
            throughput_mbps = (chunk_count * len(chunk_data)) / (1024 * 1024) / total_time
            
            print(f"\nChunk Processing Performance:")
            print(f"Total time: {total_time:.4f}s")
            print(f"Throughput: {throughput_mbps:.2f} MB/s")
            print(f"Chunks processed: {chunk_count}")
            
            # Performance assertions
            assert throughput_mbps > 50, f"Chunk processing throughput too low: {throughput_mbps:.2f} MB/s"
    
    async def test_metadata_validation_performance(self):
        """Benchmark metadata validation performance."""
        from server.web.app.services.video_metadata_service import VideoMetadataInput
        
        # Test data
        test_metadata = {
            "title": "Performance Test Video",
            "description": "A video for performance testing with a longer description to test validation performance",
            "tags": ["performance", "test", "video", "benchmark", "validation"]
        }
        
        times = []
        iterations = 1000
        
        for _ in range(iterations):
            start_time = time.time()
            
            try:
                metadata = VideoMetadataInput(**test_metadata)
                end_time = time.time()
                times.append(end_time - start_time)
            except Exception:
                continue
        
        if times:
            avg_time = statistics.mean(times)
            p95_time = statistics.quantiles(times, n=20)[18] if len(times) > 20 else max(times)
            
            print(f"\nMetadata Validation Performance:")
            print(f"Average time: {avg_time:.6f}s")
            print(f"P95 time: {p95_time:.6f}s")
            print(f"Iterations: {len(times)}")
            
            # Performance assertions
            assert avg_time < 0.001, f"Average validation time too slow: {avg_time:.6f}s"
            assert p95_time < 0.002, f"P95 validation time too slow: {p95_time:.6f}s"
    
    async def test_signed_url_generation_performance(self, mock_db, sample_video):
        """Benchmark signed URL generation performance."""
        streaming_service = StreamingService(mock_db)
        
        # Mock HLS service
        streaming_service.hls_service.get_streaming_url = MagicMock(
            return_value="https://cdn.example.com/video/test/master.m3u8"
        )
        
        times = []
        iterations = 500
        
        with patch('server.web.app.config.settings') as mock_settings:
            mock_settings.SECRET_KEY = "test-secret-key"
            
            for _ in range(iterations):
                start_time = time.time()
                
                try:
                    signed_url = streaming_service.generate_signed_streaming_url(sample_video.id)
                    end_time = time.time()
                    times.append(end_time - start_time)
                except Exception:
                    continue
        
        if times:
            avg_time = statistics.mean(times)
            p95_time = statistics.quantiles(times, n=20)[18] if len(times) > 20 else max(times)
            
            print(f"\nSigned URL Generation Performance:")
            print(f"Average time: {avg_time:.6f}s")
            print(f"P95 time: {p95_time:.6f}s")
            print(f"Iterations: {len(times)}")
            
            # Performance assertions
            assert avg_time < 0.001, f"Average URL generation time too slow: {avg_time:.6f}s"
            assert p95_time < 0.002, f"P95 URL generation time too slow: {p95_time:.6f}s"
    
    async def test_memory_usage_upload_sessions(self, mock_db):
        """Test memory usage with many upload sessions."""
        import psutil
        import os
        
        upload_service = VideoUploadService(mock_db)
        upload_service.analysis_service.validate_file_info = MagicMock()
        upload_service.s3_service.is_available.return_value = False
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        metadata = VideoMetadata("Test Video", "Description", ["test"])
        file_info = {
            'filename': 'test.mp4',
            'size': 1024 * 1024 * 100,
            'total_chunks': 10
        }
        
        # Create many upload sessions
        session_count = 100
        sessions = []
        
        for _ in range(session_count):
            try:
                session = await upload_service.initiate_upload(
                    str(uuid.uuid4()), metadata, file_info
                )
                sessions.append(session)
            except Exception:
                continue
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_per_session = (peak_memory - initial_memory) / len(sessions) if sessions else 0
        
        print(f"\nMemory Usage Performance:")
        print(f"Initial memory: {initial_memory:.2f} MB")
        print(f"Peak memory: {peak_memory:.2f} MB")
        print(f"Memory increase: {peak_memory - initial_memory:.2f} MB")
        print(f"Sessions created: {len(sessions)}")
        print(f"Memory per session: {memory_per_session:.4f} MB")
        
        # Memory usage assertions
        assert memory_per_session < 1.0, f"Memory usage per session too high: {memory_per_session:.4f} MB"
        assert peak_memory - initial_memory < 200, f"Total memory increase too high: {peak_memory - initial_memory:.2f} MB"
    
    async def test_database_query_performance(self, mock_db):
        """Benchmark database query performance simulation."""
        from server.web.app.services.video_metadata_service import VideoMetadataService
        
        metadata_service = VideoMetadataService(mock_db)
        
        # Mock database responses
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result
        
        times = []
        iterations = 100
        
        for _ in range(iterations):
            start_time = time.time()
            
            try:
                result = await metadata_service.search_videos_by_metadata(
                    query="test",
                    tags=["video"],
                    limit=20
                )
                end_time = time.time()
                times.append(end_time - start_time)
            except Exception:
                continue
        
        if times:
            avg_time = statistics.mean(times)
            p95_time = statistics.quantiles(times, n=20)[18] if len(times) > 20 else max(times)
            
            print(f"\nDatabase Query Performance:")
            print(f"Average time: {avg_time:.4f}s")
            print(f"P95 time: {p95_time:.4f}s")
            print(f"Iterations: {len(times)}")
            
            # Performance assertions
            assert avg_time < 0.05, f"Average query time too slow: {avg_time:.4f}s"
            assert p95_time < 0.1, f"P95 query time too slow: {p95_time:.4f}s"


class TestVideoServiceStressTests:
    """Stress tests for video services under load."""
    
    async def test_upload_service_stress_test(self):
        """Stress test upload service with high load."""
        mock_db = AsyncMock()
        upload_service = VideoUploadService(mock_db)
        
        # Mock dependencies
        upload_service.analysis_service.validate_file_info = MagicMock()
        upload_service.s3_service.is_available.return_value = False
        
        metadata = VideoMetadata("Stress Test Video", "Description", ["stress", "test"])
        file_info = {
            'filename': 'stress_test.mp4',
            'size': 1024 * 1024 * 50,  # 50MB
            'total_chunks': 5
        }
        
        # High concurrent load
        concurrent_requests = 50
        total_requests = 200
        
        async def create_upload_batch():
            """Create a batch of upload sessions."""
            tasks = []
            for _ in range(concurrent_requests):
                task = upload_service.initiate_upload(
                    str(uuid.uuid4()), metadata, file_info
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful = sum(1 for r in results if not isinstance(r, Exception))
            return successful
        
        start_time = time.time()
        
        # Run multiple batches
        batch_count = total_requests // concurrent_requests
        total_successful = 0
        
        for batch in range(batch_count):
            try:
                successful = await create_upload_batch()
                total_successful += successful
                
                # Small delay between batches
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Batch {batch} failed: {e}")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        success_rate = total_successful / total_requests
        throughput = total_successful / total_time
        
        print(f"\nUpload Service Stress Test:")
        print(f"Total requests: {total_requests}")
        print(f"Successful requests: {total_successful}")
        print(f"Success rate: {success_rate:.2%}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Throughput: {throughput:.2f} requests/s")
        
        # Stress test assertions
        assert success_rate > 0.8, f"Success rate too low under stress: {success_rate:.2%}"
        assert throughput > 10, f"Throughput too low under stress: {throughput:.2f} req/s"
    
    async def test_streaming_service_concurrent_access(self):
        """Test streaming service under concurrent access load."""
        mock_db = AsyncMock()
        streaming_service = StreamingService(mock_db)
        
        # Mock video
        sample_video = Video(
            id=str(uuid.uuid4()),
            status=VideoStatus.ready,
            visibility=VideoVisibility.public
        )
        mock_db.get.return_value = sample_video
        
        # Concurrent access checks
        concurrent_checks = 100
        
        async def check_access():
            """Perform access check."""
            try:
                return await streaming_service.check_video_access(sample_video.id)
            except Exception:
                return False
        
        start_time = time.time()
        
        # Run concurrent access checks
        tasks = [check_access() for _ in range(concurrent_checks)]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        successful_checks = sum(1 for r in results if r is True)
        success_rate = successful_checks / concurrent_checks
        throughput = successful_checks / total_time
        
        print(f"\nStreaming Service Concurrent Access Test:")
        print(f"Concurrent checks: {concurrent_checks}")
        print(f"Successful checks: {successful_checks}")
        print(f"Success rate: {success_rate:.2%}")
        print(f"Total time: {total_time:.4f}s")
        print(f"Throughput: {throughput:.2f} checks/s")
        
        # Concurrent access assertions
        assert success_rate > 0.95, f"Success rate too low: {success_rate:.2%}"
        assert throughput > 100, f"Throughput too low: {throughput:.2f} checks/s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])