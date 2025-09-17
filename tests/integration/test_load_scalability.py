"""
Load testing for system scalability.
"""
import pytest
import asyncio
import time
import uuid
import statistics
from unittest.mock import AsyncMock, MagicMock
from concurrent.futures import ThreadPoolExecutor

from server.web.app.services.video_upload_service import VideoUploadService, VideoMetadata
from server.web.app.services.streaming_service import StreamingService
from server.web.app.services.video_transcoding_service import VideoTranscodingService
from server.web.app.models import Video, VideoStatus, VideoVisibility, User
from tests.mocks import create_mock_s3_service


class TestUploadLoadTesting:
    """Load testing for video upload services."""
    
    @pytest.fixture
    async def mock_db(self):
        """Mock database session optimized for load testing."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.get = AsyncMock()
        return db
    
    @pytest.fixture
    def upload_service(self, mock_db):
        """Create upload service for load testing."""
        service = VideoUploadService(mock_db)
        service.s3_service = create_mock_s3_service()
        service.analysis_service = MagicMock()
        service.analysis_service.validate_file_info = MagicMock()
        return service
    
    async def test_high_volume_upload_initiation(self, upload_service, mock_db):
        """Test high volume upload initiation."""
        
        # Test parameters
        concurrent_uploads = 100
        total_uploads = 500
        batch_size = 50
        
        # Prepare test data
        users = [str(uuid.uuid4()) for _ in range(20)]  # 20 users
        metadata = VideoMetadata("Load Test Video", "Description", ["load", "test"])
        file_info = {
            'filename': 'load_test.mp4',
            'size': 1024 * 1024 * 25,  # 25MB
            'total_chunks': 5
        }
        
        async def initiate_upload_batch(batch_start, batch_size):
            """Initiate a batch of uploads."""
            batch_results = []
            
            for i in range(batch_start, min(batch_start + batch_size, total_uploads)):
                user_id = users[i % len(users)]
                video_id = str(uuid.uuid4())
                
                # Mock video for this upload
                mock_video = Video(
                    id=video_id,
                    creator_id=user_id,
                    title=f"Load Test Video {i}",
                    status=VideoStatus.uploading
                )
                mock_db.get.return_value = mock_video
                
                try:
                    start_time = time.time()
                    session = await upload_service.initiate_upload(user_id, metadata, file_info)
                    end_time = time.time()
                    
                    batch_results.append({
                        'upload_id': i,
                        'success': True,
                        'duration': end_time - start_time,
                        'session_id': session.session_id
                    })
                except Exception as e:
                    batch_results.append({
                        'upload_id': i,
                        'success': False,
                        'error': str(e),
                        'duration': 0
                    })
            
            return batch_results
        
        # Execute load test in batches
        all_results = []
        overall_start_time = time.time()
        
        for batch_start in range(0, total_uploads, batch_size):
            batch_results = await initiate_upload_batch(batch_start, batch_size)
            all_results.extend(batch_results)
            
            # Small delay between batches to prevent overwhelming
            await asyncio.sleep(0.1)
        
        overall_end_time = time.time()
        
        # Analyze results
        successful_uploads = [r for r in all_results if r['success']]
        failed_uploads = [r for r in all_results if not r['success']]
        
        durations = [r['duration'] for r in successful_uploads]
        
        total_time = overall_end_time - overall_start_time
        throughput = len(successful_uploads) / total_time
        
        avg_duration = statistics.mean(durations) if durations else 0
        p95_duration = statistics.quantiles(durations, n=20)[18] if len(durations) > 20 else max(durations) if durations else 0
        
        print(f"\nHigh Volume Upload Initiation Results:")
        print(f"  Total uploads attempted: {total_uploads}")
        print(f"  Successful uploads: {len(successful_uploads)}")
        print(f"  Failed uploads: {len(failed_uploads)}")
        print(f"  Success rate: {len(successful_uploads)/total_uploads:.2%}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Throughput: {throughput:.2f} uploads/s")
        print(f"  Average duration: {avg_duration:.4f}s")
        print(f"  P95 duration: {p95_duration:.4f}s")
        
        # Performance assertions
        assert len(successful_uploads) >= total_uploads * 0.9  # 90% success rate
        assert throughput > 20  # At least 20 uploads per second
        assert avg_duration < 0.1  # Average under 100ms
        assert p95_duration < 0.2  # P95 under 200ms
    
    async def test_concurrent_chunk_processing_load(self, upload_service):
        """Test concurrent chunk processing under load."""
        
        # Create multiple upload sessions
        session_count = 20
        chunks_per_session = 10
        chunk_size = 1024 * 1024  # 1MB chunks
        
        sessions = []
        for i in range(session_count):
            session_id = str(uuid.uuid4())
            video_id = str(uuid.uuid4())
            user_id = str(uuid.uuid4())
            
            from server.web.app.services.video_upload_service import UploadSession
            session = UploadSession(
                session_id=session_id,
                video_id=video_id,
                user_id=user_id,
                metadata={'filename': f'load_test_{i}.mp4', 'total_chunks': chunks_per_session}
            )
            session.temp_file_path = f"/tmp/load_test_{i}.tmp"
            
            upload_service.active_sessions[session_id] = session
            sessions.append(session)
        
        # Prepare chunk data
        chunk_data = b"x" * chunk_size
        
        async def process_all_chunks_for_session(session):
            """Process all chunks for a single session."""
            session_results = []
            
            with patch('aiofiles.open'):
                for chunk_num in range(chunks_per_session):
                    try:
                        start_time = time.time()
                        result = await upload_service.process_chunk(
                            session.session_id, chunk_data, chunk_num + 1
                        )
                        end_time = time.time()
                        
                        session_results.append({
                            'session_id': session.session_id,
                            'chunk_num': chunk_num + 1,
                            'success': result.success,
                            'duration': end_time - start_time
                        })
                    except Exception as e:
                        session_results.append({
                            'session_id': session.session_id,
                            'chunk_num': chunk_num + 1,
                            'success': False,
                            'error': str(e),
                            'duration': 0
                        })
            
            return session_results
        
        # Execute concurrent chunk processing
        start_time = time.time()
        tasks = [process_all_chunks_for_session(session) for session in sessions]
        all_session_results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Flatten results
        all_results = [result for session_results in all_session_results for result in session_results]
        
        # Analyze results
        successful_chunks = [r for r in all_results if r['success']]
        failed_chunks = [r for r in all_results if not r['success']]
        
        total_time = end_time - start_time
        total_data_processed = len(successful_chunks) * chunk_size
        throughput_mbps = (total_data_processed / (1024 * 1024)) / total_time
        
        durations = [r['duration'] for r in successful_chunks]
        avg_duration = statistics.mean(durations) if durations else 0
        
        print(f"\nConcurrent Chunk Processing Load Results:")
        print(f"  Total chunks: {len(all_results)}")
        print(f"  Successful chunks: {len(successful_chunks)}")
        print(f"  Failed chunks: {len(failed_chunks)}")
        print(f"  Success rate: {len(successful_chunks)/len(all_results):.2%}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Throughput: {throughput_mbps:.2f} MB/s")
        print(f"  Average chunk duration: {avg_duration:.4f}s")
        
        # Performance assertions
        assert len(successful_chunks) >= len(all_results) * 0.95  # 95% success rate
        assert throughput_mbps > 50  # At least 50 MB/s throughput
        assert avg_duration < 0.05  # Average under 50ms per chunk
    
    async def test_memory_usage_under_load(self, upload_service, mock_db):
        """Test memory usage under high load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create many concurrent upload sessions
        session_count = 200
        sessions_created = []
        
        metadata = VideoMetadata("Memory Test Video", "Description", ["memory", "test"])
        file_info = {
            'filename': 'memory_test.mp4',
            'size': 1024 * 1024 * 10,  # 10MB
            'total_chunks': 5
        }
        
        # Create sessions in batches to monitor memory growth
        batch_size = 50
        memory_measurements = []
        
        for batch_start in range(0, session_count, batch_size):
            batch_sessions = []
            
            for i in range(batch_start, min(batch_start + batch_size, session_count)):
                user_id = str(uuid.uuid4())
                video_id = str(uuid.uuid4())
                
                mock_video = Video(
                    id=video_id,
                    creator_id=user_id,
                    title=f"Memory Test Video {i}",
                    status=VideoStatus.uploading
                )
                mock_db.get.return_value = mock_video
                
                try:
                    session = await upload_service.initiate_upload(user_id, metadata, file_info)
                    batch_sessions.append(session)
                except Exception:
                    pass  # Continue with memory test
            
            sessions_created.extend(batch_sessions)
            
            # Measure memory after each batch
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_measurements.append({
                'sessions_count': len(sessions_created),
                'memory_mb': current_memory,
                'memory_increase': current_memory - initial_memory
            })
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_memory_increase = final_memory - initial_memory
        memory_per_session = total_memory_increase / len(sessions_created) if sessions_created else 0
        
        print(f"\nMemory Usage Under Load Results:")
        print(f"  Sessions created: {len(sessions_created)}")
        print(f"  Initial memory: {initial_memory:.2f} MB")
        print(f"  Final memory: {final_memory:.2f} MB")
        print(f"  Total memory increase: {total_memory_increase:.2f} MB")
        print(f"  Memory per session: {memory_per_session:.4f} MB")
        
        # Memory usage assertions
        assert memory_per_session < 2.0  # Less than 2MB per session
        assert total_memory_increase < 400  # Less than 400MB total increase
        
        # Clean up sessions to test memory release
        cleanup_start_memory = process.memory_info().rss / 1024 / 1024
        
        # Cancel all sessions
        for session in sessions_created:
            try:
                await upload_service.cancel_upload(session.session_id)
            except Exception:
                pass
        
        # Force garbage collection
        import gc
        gc.collect()
        
        cleanup_end_memory = process.memory_info().rss / 1024 / 1024
        memory_released = cleanup_start_memory - cleanup_end_memory
        
        print(f"  Memory after cleanup: {cleanup_end_memory:.2f} MB")
        print(f"  Memory released: {memory_released:.2f} MB")
        
        # Should release significant memory
        assert memory_released > total_memory_increase * 0.5  # At least 50% released


class TestStreamingLoadTesting:
    """Load testing for video streaming services."""
    
    @pytest.fixture
    async def mock_db(self):
        """Mock database session for streaming load tests."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.get = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    @pytest.fixture
    def streaming_service(self, mock_db):
        """Create streaming service for load testing."""
        service = StreamingService(mock_db)
        service.hls_service = MagicMock()
        return service
    
    async def test_high_concurrent_streaming_load(self, streaming_service, mock_db):
        """Test high concurrent streaming load."""
        
        # Test parameters
        concurrent_viewers = 200
        videos_count = 20
        
        # Create videos
        videos = []
        for i in range(videos_count):
            video = Video(
                id=str(uuid.uuid4()),
                creator_id=str(uuid.uuid4()),
                title=f"Load Test Video {i}",
                status=VideoStatus.ready,
                visibility=VideoVisibility.public,
                duration_seconds=300
            )
            videos.append(video)
        
        async def simulate_concurrent_viewer(viewer_id):
            """Simulate a concurrent viewer."""
            try:
                # Select random video
                video = videos[hash(viewer_id) % len(videos)]
                mock_db.get.return_value = video
                
                # Check access
                start_time = time.time()
                has_access = await streaming_service.check_video_access(video.id, viewer_id)
                access_time = time.time() - start_time
                
                if not has_access:
                    return {'viewer_id': viewer_id, 'success': False, 'stage': 'access_denied'}
                
                # Create viewing session
                session_start_time = time.time()
                session = await streaming_service.create_viewing_session(
                    video_id=video.id,
                    user_id=viewer_id,
                    ip_address=f"10.0.{hash(viewer_id) % 255}.{hash(viewer_id) % 255}"
                )
                session_time = time.time() - session_start_time
                
                # Mock session retrieval for progress updates
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = session
                mock_db.execute.return_value = mock_result
                
                # Simulate viewing with progress updates
                update_times = []
                for position in [60, 120, 180, 240]:
                    update_start_time = time.time()
                    
                    progress_data = {
                        'current_position_seconds': float(position),
                        'completion_percentage': (position / 300) * 100,
                        'quality_switches': position // 120,
                        'buffering_events': position // 180
                    }
                    
                    await streaming_service.update_viewing_progress(
                        session.session_token, video.id, progress_data
                    )
                    
                    update_time = time.time() - update_start_time
                    update_times.append(update_time)
                
                return {
                    'viewer_id': viewer_id,
                    'success': True,
                    'access_time': access_time,
                    'session_time': session_time,
                    'avg_update_time': statistics.mean(update_times),
                    'total_updates': len(update_times)
                }
                
            except Exception as e:
                return {
                    'viewer_id': viewer_id,
                    'success': False,
                    'error': str(e)
                }
        
        # Execute concurrent streaming load test
        viewers = [str(uuid.uuid4()) for _ in range(concurrent_viewers)]
        
        start_time = time.time()
        tasks = [simulate_concurrent_viewer(viewer) for viewer in viewers]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Analyze results
        successful_viewers = [r for r in results if r['success']]
        failed_viewers = [r for r in results if not r['success']]
        
        total_time = end_time - start_time
        
        # Calculate performance metrics
        access_times = [r['access_time'] for r in successful_viewers]
        session_times = [r['session_time'] for r in successful_viewers]
        update_times = [r['avg_update_time'] for r in successful_viewers]
        
        avg_access_time = statistics.mean(access_times) if access_times else 0
        avg_session_time = statistics.mean(session_times) if session_times else 0
        avg_update_time = statistics.mean(update_times) if update_times else 0
        
        throughput = len(successful_viewers) / total_time
        
        print(f"\nHigh Concurrent Streaming Load Results:")
        print(f"  Concurrent viewers: {concurrent_viewers}")
        print(f"  Successful viewers: {len(successful_viewers)}")
        print(f"  Failed viewers: {len(failed_viewers)}")
        print(f"  Success rate: {len(successful_viewers)/concurrent_viewers:.2%}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Throughput: {throughput:.2f} viewers/s")
        print(f"  Average access time: {avg_access_time:.4f}s")
        print(f"  Average session time: {avg_session_time:.4f}s")
        print(f"  Average update time: {avg_update_time:.4f}s")
        
        # Performance assertions
        assert len(successful_viewers) >= concurrent_viewers * 0.95  # 95% success rate
        assert throughput > 50  # At least 50 viewers per second
        assert avg_access_time < 0.05  # Access check under 50ms
        assert avg_session_time < 0.1   # Session creation under 100ms
        assert avg_update_time < 0.05   # Progress updates under 50ms
    
    async def test_streaming_scalability_limits(self, streaming_service, mock_db):
        """Test streaming service scalability limits."""
        
        # Gradually increase load to find limits
        load_levels = [50, 100, 200, 400, 800]
        scalability_results = []
        
        # Create a single video for all tests
        video = Video(
            id=str(uuid.uuid4()),
            creator_id=str(uuid.uuid4()),
            title="Scalability Test Video",
            status=VideoStatus.ready,
            visibility=VideoVisibility.public,
            duration_seconds=120
        )
        mock_db.get.return_value = video
        
        for load_level in load_levels:
            print(f"\nTesting load level: {load_level} concurrent viewers")
            
            async def quick_access_check(viewer_id):
                """Quick access check for scalability testing."""
                try:
                    start_time = time.time()
                    has_access = await streaming_service.check_video_access(video.id, viewer_id)
                    end_time = time.time()
                    
                    return {
                        'success': has_access,
                        'duration': end_time - start_time
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'error': str(e),
                        'duration': 0
                    }
            
            # Generate viewers for this load level
            viewers = [str(uuid.uuid4()) for _ in range(load_level)]
            
            # Execute load test
            start_time = time.time()
            tasks = [quick_access_check(viewer) for viewer in viewers]
            results = await asyncio.gather(*tasks)
            end_time = time.time()
            
            # Analyze results for this load level
            successful_checks = [r for r in results if r['success']]
            failed_checks = [r for r in results if not r['success']]
            
            durations = [r['duration'] for r in successful_checks]
            
            total_time = end_time - start_time
            success_rate = len(successful_checks) / load_level
            throughput = len(successful_checks) / total_time
            avg_duration = statistics.mean(durations) if durations else 0
            p95_duration = statistics.quantiles(durations, n=20)[18] if len(durations) > 20 else max(durations) if durations else 0
            
            scalability_results.append({
                'load_level': load_level,
                'success_rate': success_rate,
                'throughput': throughput,
                'avg_duration': avg_duration,
                'p95_duration': p95_duration,
                'total_time': total_time
            })
            
            print(f"  Success rate: {success_rate:.2%}")
            print(f"  Throughput: {throughput:.2f} checks/s")
            print(f"  Avg duration: {avg_duration:.4f}s")
            print(f"  P95 duration: {p95_duration:.4f}s")
            
            # Stop if performance degrades significantly
            if success_rate < 0.8 or avg_duration > 0.1:
                print(f"  Performance degradation detected at {load_level} concurrent viewers")
                break
        
        # Analyze scalability trends
        print(f"\nScalability Analysis:")
        for result in scalability_results:
            print(f"  Load {result['load_level']:3d}: "
                  f"Success {result['success_rate']:.1%}, "
                  f"Throughput {result['throughput']:6.1f}/s, "
                  f"Avg {result['avg_duration']:.4f}s")
        
        # Find maximum sustainable load
        sustainable_loads = [r for r in scalability_results if r['success_rate'] >= 0.95 and r['avg_duration'] <= 0.05]
        max_sustainable_load = max(sustainable_loads, key=lambda x: x['load_level'])['load_level'] if sustainable_loads else 0
        
        print(f"\nMaximum sustainable load: {max_sustainable_load} concurrent viewers")
        
        # Assertions
        assert max_sustainable_load >= 100  # Should handle at least 100 concurrent viewers
        assert len(scalability_results) > 0  # Should complete at least one load level


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])