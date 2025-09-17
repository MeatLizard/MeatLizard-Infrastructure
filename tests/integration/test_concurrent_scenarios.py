"""
Integration tests for concurrent upload and streaming scenarios.
"""
import pytest
import asyncio
import uuid
import time
from unittest.mock import AsyncMock, MagicMock
from concurrent.futures import ThreadPoolExecutor

from server.web.app.services.video_upload_service import VideoUploadService, VideoMetadata
from server.web.app.services.streaming_service import StreamingService
from server.web.app.services.video_transcoding_service import VideoTranscodingService
from server.web.app.models import Video, VideoStatus, VideoVisibility, User
from tests.mocks import create_mock_s3_service


class TestConcurrentUploadScenarios:
    """Test concurrent upload scenarios."""
    
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
    
    @pytest.fixture
    def upload_service(self, mock_db):
        """Create upload service with mocked dependencies."""
        service = VideoUploadService(mock_db)
        service.s3_service = create_mock_s3_service()
        service.analysis_service = MagicMock()
        service.analysis_service.validate_file_info = MagicMock()
        return service
    
    async def test_concurrent_upload_initiation(self, upload_service, mock_db):
        """Test concurrent upload initiation."""
        
        # Create multiple users
        users = [
            User(id=str(uuid.uuid4()), display_label=f"User {i}")
            for i in range(5)
        ]
        
        # Prepare upload data
        metadata = VideoMetadata("Concurrent Test Video", "Description", ["test"])
        file_info = {
            'filename': 'test.mp4',
            'size': 1024 * 1024 * 50,  # 50MB
            'total_chunks': 10
        }
        
        async def initiate_upload_for_user(user):
            """Initiate upload for a single user."""
            video_id = str(uuid.uuid4())
            mock_video = Video(
                id=video_id,
                creator_id=user.id,
                title="Concurrent Test Video",
                status=VideoStatus.uploading
            )
            
            # Mock database response for this specific call
            mock_db.get.return_value = mock_video
            
            try:
                session = await upload_service.initiate_upload(user.id, metadata, file_info)
                return {'success': True, 'session': session, 'user_id': user.id}
            except Exception as e:
                return {'success': False, 'error': str(e), 'user_id': user.id}
        
        # Execute concurrent uploads
        start_time = time.time()
        tasks = [initiate_upload_for_user(user) for user in users]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Analyze results
        successful_uploads = [r for r in results if r['success']]
        failed_uploads = [r for r in results if not r['success']]
        
        total_time = end_time - start_time
        
        print(f"\nConcurrent Upload Initiation Results:")
        print(f"  Total uploads: {len(results)}")
        print(f"  Successful: {len(successful_uploads)}")
        print(f"  Failed: {len(failed_uploads)}")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Average time per upload: {total_time/len(results):.3f}s")
        
        # Assertions
        assert len(successful_uploads) >= len(users) * 0.8  # At least 80% success
        assert total_time < 5.0  # Should complete within 5 seconds
        
        # Verify all sessions are unique
        session_ids = [r['session'].session_id for r in successful_uploads]
        assert len(set(session_ids)) == len(successful_uploads)
    
    async def test_concurrent_chunk_processing(self, upload_service):
        """Test concurrent chunk processing for multiple uploads."""
        
        # Create multiple upload sessions
        session_count = 3
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
                metadata={'filename': f'test_{i}.mp4', 'total_chunks': 5}
            )
            session.temp_file_path = f"/tmp/test_{i}.tmp"
            
            upload_service.active_sessions[session_id] = session
            sessions.append(session)
        
        # Prepare chunk data
        chunk_size = 1024 * 1024  # 1MB chunks
        chunk_data = b"x" * chunk_size
        
        async def process_chunks_for_session(session):
            """Process chunks for a single session."""
            results = []
            
            with patch('aiofiles.open'):
                for chunk_num in range(5):  # 5 chunks per session
                    try:
                        result = await upload_service.process_chunk(
                            session.session_id, chunk_data, chunk_num + 1
                        )
                        results.append(result)
                    except Exception as e:
                        results.append(e)
            
            return results
        
        # Execute concurrent chunk processing
        start_time = time.time()
        tasks = [process_chunks_for_session(session) for session in sessions]
        all_results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Analyze results
        total_chunks = sum(len(results) for results in all_results)
        successful_chunks = sum(
            len([r for r in results if hasattr(r, 'success') and r.success])
            for results in all_results
        )
        
        total_time = end_time - start_time
        throughput = (successful_chunks * chunk_size) / (1024 * 1024) / total_time  # MB/s
        
        print(f"\nConcurrent Chunk Processing Results:")
        print(f"  Total chunks: {total_chunks}")
        print(f"  Successful chunks: {successful_chunks}")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Throughput: {throughput:.2f} MB/s")
        
        # Assertions
        assert successful_chunks >= total_chunks * 0.9  # At least 90% success
        assert throughput > 10  # At least 10 MB/s throughput
    
    async def test_mixed_upload_operations(self, upload_service, mock_db):
        """Test mixed upload operations (initiate, process, complete)."""
        
        # Create different types of operations
        operations = []
        
        # Operation 1: New upload initiation
        async def initiate_new_upload():
            user_id = str(uuid.uuid4())
            video_id = str(uuid.uuid4())
            
            mock_video = Video(
                id=video_id,
                creator_id=user_id,
                title="Mixed Test Video",
                status=VideoStatus.uploading
            )
            mock_db.get.return_value = mock_video
            
            metadata = VideoMetadata("Mixed Test Video", "Description", ["test"])
            file_info = {'filename': 'test.mp4', 'size': 1024 * 1024 * 10, 'total_chunks': 5}
            
            return await upload_service.initiate_upload(user_id, metadata, file_info)
        
        # Operation 2: Chunk processing for existing session
        async def process_existing_chunks():
            session_id = str(uuid.uuid4())
            session = MagicMock()
            session.session_id = session_id
            session.temp_file_path = "/tmp/test.tmp"
            upload_service.active_sessions[session_id] = session
            
            chunk_data = b"x" * (1024 * 1024)  # 1MB
            
            with patch('aiofiles.open'):
                results = []
                for i in range(3):
                    result = await upload_service.process_chunk(session_id, chunk_data, i + 1)
                    results.append(result)
                return results
        
        # Operation 3: Upload completion
        async def complete_existing_upload():
            session_id = str(uuid.uuid4())
            video_id = str(uuid.uuid4())
            
            session = MagicMock()
            session.session_id = session_id
            session.video_id = video_id
            session.temp_file_path = "/tmp/complete_test.tmp"
            upload_service.active_sessions[session_id] = session
            
            mock_video = Video(id=video_id, status=VideoStatus.uploading)
            mock_db.get.return_value = mock_video
            
            with patch('os.path.exists', return_value=True):
                with patch('os.rename'):
                    with patch.object(upload_service.analysis_service, 'analyze_video_file') as mock_analyze:
                        mock_analyze.return_value.is_valid = True
                        mock_analyze.return_value.duration_seconds = 120.0
                        
                        return await upload_service.complete_upload(session_id, ["720p_30fps"])
        
        # Create mixed operations
        operations = [
            initiate_new_upload(),
            process_existing_chunks(),
            complete_existing_upload(),
            initiate_new_upload(),  # Another initiation
            process_existing_chunks()  # Another chunk processing
        ]
        
        # Execute mixed operations concurrently
        start_time = time.time()
        results = await asyncio.gather(*operations, return_exceptions=True)
        end_time = time.time()
        
        # Analyze results
        successful_ops = [r for r in results if not isinstance(r, Exception)]
        failed_ops = [r for r in results if isinstance(r, Exception)]
        
        total_time = end_time - start_time
        
        print(f"\nMixed Upload Operations Results:")
        print(f"  Total operations: {len(results)}")
        print(f"  Successful: {len(successful_ops)}")
        print(f"  Failed: {len(failed_ops)}")
        print(f"  Total time: {total_time:.3f}s")
        
        # Assertions
        assert len(successful_ops) >= len(operations) * 0.7  # At least 70% success
        assert total_time < 10.0  # Should complete within 10 seconds


class TestConcurrentStreamingScenarios:
    """Test concurrent streaming scenarios."""
    
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
    
    @pytest.fixture
    def streaming_service(self, mock_db):
        """Create streaming service."""
        service = StreamingService(mock_db)
        service.hls_service = MagicMock()
        return service
    
    async def test_concurrent_access_checks(self, streaming_service, mock_db):
        """Test concurrent video access checks."""
        
        # Create multiple videos
        videos = []
        for i in range(10):
            video = Video(
                id=str(uuid.uuid4()),
                creator_id=str(uuid.uuid4()),
                title=f"Concurrent Video {i}",
                status=VideoStatus.ready,
                visibility=VideoVisibility.public
            )
            videos.append(video)
        
        async def check_access_for_video(video):
            """Check access for a single video."""
            mock_db.get.return_value = video
            
            try:
                return await streaming_service.check_video_access(video.id)
            except Exception as e:
                return e
        
        # Create concurrent access checks
        concurrent_checks = 50
        tasks = []
        
        for i in range(concurrent_checks):
            video = videos[i % len(videos)]  # Distribute across videos
            task = check_access_for_video(video)
            tasks.append(task)
        
        # Execute concurrent checks
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Analyze results
        successful_checks = [r for r in results if r is True]
        failed_checks = [r for r in results if isinstance(r, Exception)]
        
        total_time = end_time - start_time
        throughput = len(successful_checks) / total_time
        
        print(f"\nConcurrent Access Checks Results:")
        print(f"  Total checks: {len(results)}")
        print(f"  Successful: {len(successful_checks)}")
        print(f"  Failed: {len(failed_checks)}")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Throughput: {throughput:.2f} checks/s")
        
        # Assertions
        assert len(successful_checks) >= concurrent_checks * 0.95  # 95% success rate
        assert throughput > 50  # At least 50 checks per second
    
    async def test_concurrent_viewing_sessions(self, streaming_service, mock_db):
        """Test concurrent viewing session creation and management."""
        
        # Create a video
        video_id = str(uuid.uuid4())
        mock_video = Video(
            id=video_id,
            creator_id=str(uuid.uuid4()),
            title="Concurrent Streaming Video",
            status=VideoStatus.ready,
            duration_seconds=120
        )
        
        # Create multiple users
        users = [str(uuid.uuid4()) for _ in range(20)]
        
        async def create_and_manage_session(user_id):
            """Create and manage a viewing session for a user."""
            try:
                # Create session
                session = await streaming_service.create_viewing_session(
                    video_id=video_id,
                    user_id=user_id,
                    ip_address=f"192.168.1.{hash(user_id) % 255}",
                    user_agent="Test Browser"
                )
                
                # Mock session retrieval for updates
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = session
                mock_db.execute.return_value = mock_result
                
                # Simulate viewing progress updates
                progress_updates = [
                    {'current_position_seconds': 30.0, 'completion_percentage': 25.0},
                    {'current_position_seconds': 60.0, 'completion_percentage': 50.0},
                    {'current_position_seconds': 90.0, 'completion_percentage': 75.0}
                ]
                
                for progress in progress_updates:
                    await streaming_service.update_viewing_progress(
                        session.session_token, video_id, progress
                    )
                    
                    # Small delay to simulate real viewing
                    await asyncio.sleep(0.01)
                
                # End session
                final_data = {
                    'current_position_seconds': 120.0,
                    'completion_percentage': 100.0
                }
                
                await streaming_service.end_viewing_session(
                    session.session_token, video_id, final_data
                )
                
                return {'success': True, 'user_id': user_id, 'session_token': session.session_token}
                
            except Exception as e:
                return {'success': False, 'user_id': user_id, 'error': str(e)}
        
        # Execute concurrent sessions
        start_time = time.time()
        tasks = [create_and_manage_session(user_id) for user_id in users]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Analyze results
        successful_sessions = [r for r in results if r['success']]
        failed_sessions = [r for r in results if not r['success']]
        
        total_time = end_time - start_time
        
        print(f"\nConcurrent Viewing Sessions Results:")
        print(f"  Total sessions: {len(results)}")
        print(f"  Successful: {len(successful_sessions)}")
        print(f"  Failed: {len(failed_sessions)}")
        print(f"  Total time: {total_time:.3f}s")
        
        # Assertions
        assert len(successful_sessions) >= len(users) * 0.9  # 90% success rate
        assert total_time < 15.0  # Should complete within 15 seconds
        
        # Verify all sessions are unique
        session_tokens = [r['session_token'] for r in successful_sessions]
        assert len(set(session_tokens)) == len(successful_sessions)
    
    async def test_concurrent_streaming_with_quality_switches(self, streaming_service, mock_db):
        """Test concurrent streaming with quality switching."""
        
        # Setup video and HLS service
        video_id = str(uuid.uuid4())
        mock_video = Video(
            id=video_id,
            creator_id=str(uuid.uuid4()),
            title="Quality Switch Video",
            status=VideoStatus.ready,
            duration_seconds=300
        )
        
        streaming_service.hls_service.get_available_qualities.return_value = [
            {"quality_preset": "480p_30fps", "height": 480},
            {"quality_preset": "720p_30fps", "height": 720},
            {"quality_preset": "1080p_30fps", "height": 1080}
        ]
        
        async def simulate_viewer_with_quality_switches(viewer_id):
            """Simulate a viewer with quality switching behavior."""
            try:
                # Create session
                session = await streaming_service.create_viewing_session(
                    video_id=video_id,
                    user_id=viewer_id,
                    ip_address=f"10.0.0.{hash(viewer_id) % 255}"
                )
                
                # Mock session retrieval
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = session
                mock_db.execute.return_value = mock_result
                
                # Simulate viewing with quality switches
                quality_switches = 0
                current_quality = "720p_30fps"
                
                for position in [60, 120, 180, 240]:
                    # Randomly switch quality
                    if position % 120 == 0:  # Switch every 2 minutes
                        quality_switches += 1
                        current_quality = "1080p_30fps" if current_quality == "720p_30fps" else "720p_30fps"
                    
                    progress_data = {
                        'current_position_seconds': float(position),
                        'completion_percentage': (position / 300) * 100,
                        'quality_switches': quality_switches,
                        'buffering_events': quality_switches  # Assume buffering on quality switch
                    }
                    
                    await streaming_service.update_viewing_progress(
                        session.session_token, video_id, progress_data
                    )
                    
                    await asyncio.sleep(0.005)  # Small delay
                
                return {
                    'success': True,
                    'viewer_id': viewer_id,
                    'quality_switches': quality_switches,
                    'session_token': session.session_token
                }
                
            except Exception as e:
                return {'success': False, 'viewer_id': viewer_id, 'error': str(e)}
        
        # Create concurrent viewers
        viewer_count = 15
        viewers = [str(uuid.uuid4()) for _ in range(viewer_count)]
        
        # Execute concurrent streaming
        start_time = time.time()
        tasks = [simulate_viewer_with_quality_switches(viewer) for viewer in viewers]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Analyze results
        successful_streams = [r for r in results if r['success']]
        failed_streams = [r for r in results if not r['success']]
        
        total_quality_switches = sum(r['quality_switches'] for r in successful_streams)
        total_time = end_time - start_time
        
        print(f"\nConcurrent Streaming with Quality Switches Results:")
        print(f"  Total viewers: {len(results)}")
        print(f"  Successful streams: {len(successful_streams)}")
        print(f"  Failed streams: {len(failed_streams)}")
        print(f"  Total quality switches: {total_quality_switches}")
        print(f"  Total time: {total_time:.3f}s")
        
        # Assertions
        assert len(successful_streams) >= viewer_count * 0.9  # 90% success rate
        assert total_quality_switches > 0  # Should have some quality switches
        assert total_time < 20.0  # Should complete within 20 seconds


class TestConcurrentTranscodingScenarios:
    """Test concurrent transcoding scenarios."""
    
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
    
    @pytest.fixture
    def transcoding_service(self, mock_db):
        """Create transcoding service."""
        service = VideoTranscodingService(mock_db, "redis://localhost:6379")
        service.redis_client = AsyncMock()
        return service
    
    async def test_concurrent_job_queueing(self, transcoding_service):
        """Test concurrent transcoding job queueing."""
        
        # Create multiple videos with different quality requirements
        videos = []
        for i in range(10):
            video_data = {
                'video_id': str(uuid.uuid4()),
                'quality_presets': ['480p_30fps', '720p_30fps', '1080p_30fps']
            }
            videos.append(video_data)
        
        async def queue_jobs_for_video(video_data):
            """Queue transcoding jobs for a single video."""
            jobs = []
            
            for preset in video_data['quality_presets']:
                try:
                    job = await transcoding_service.queue_transcoding_job(
                        video_id=video_data['video_id'],
                        quality_preset=preset,
                        target_resolution="1280x720" if "720p" in preset else "1920x1080",
                        target_framerate=30,
                        target_bitrate=2500 if "720p" in preset else 5000
                    )
                    jobs.append({'success': True, 'preset': preset})
                except Exception as e:
                    jobs.append({'success': False, 'preset': preset, 'error': str(e)})
            
            return jobs
        
        # Execute concurrent job queueing
        start_time = time.time()
        tasks = [queue_jobs_for_video(video) for video in videos]
        all_results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Flatten results
        all_jobs = [job for video_jobs in all_results for job in video_jobs]
        successful_jobs = [job for job in all_jobs if job['success']]
        failed_jobs = [job for job in all_jobs if not job['success']]
        
        total_time = end_time - start_time
        
        print(f"\nConcurrent Job Queueing Results:")
        print(f"  Total jobs: {len(all_jobs)}")
        print(f"  Successful: {len(successful_jobs)}")
        print(f"  Failed: {len(failed_jobs)}")
        print(f"  Total time: {total_time:.3f}s")
        
        # Assertions
        assert len(successful_jobs) >= len(all_jobs) * 0.95  # 95% success rate
        assert total_time < 5.0  # Should complete within 5 seconds
        
        # Verify Redis operations
        expected_calls = len(successful_jobs)
        assert transcoding_service.redis_client.lpush.call_count >= expected_calls * 0.9
    
    async def test_concurrent_job_processing(self, transcoding_service, mock_db):
        """Test concurrent job processing simulation."""
        
        # Create mock jobs
        jobs = []
        for i in range(20):
            job_data = {
                "job_id": str(uuid.uuid4()),
                "video_id": str(uuid.uuid4()),
                "quality_preset": f"720p_30fps",
                "retry_count": 0
            }
            jobs.append(job_data)
        
        async def process_single_job(job_data):
            """Process a single transcoding job."""
            try:
                # Mock job retrieval
                transcoding_service.redis_client.brpop.return_value = ("queue", str(job_data))
                
                # Get next job
                next_job = await transcoding_service.get_next_job()
                
                if not next_job:
                    return {'success': False, 'job_id': job_data['job_id'], 'error': 'No job found'}
                
                # Mark as processing
                mock_result = MagicMock()
                mock_result.rowcount = 1
                mock_db.execute.return_value = mock_result
                
                processing_success = await transcoding_service.mark_job_processing(job_data['job_id'])
                
                if not processing_success:
                    return {'success': False, 'job_id': job_data['job_id'], 'error': 'Failed to mark processing'}
                
                # Simulate progress updates
                for progress in [25, 50, 75, 100]:
                    await transcoding_service.update_job_progress(job_data['job_id'], progress)
                    await asyncio.sleep(0.01)  # Small delay
                
                # Complete job
                completion_success = await transcoding_service.complete_job(
                    job_id=job_data['job_id'],
                    output_s3_key=f"output/{job_data['job_id']}.mp4",
                    hls_manifest_s3_key=f"hls/{job_data['job_id']}/playlist.m3u8",
                    output_file_size=1024 * 1024 * 50  # 50MB
                )
                
                return {
                    'success': completion_success,
                    'job_id': job_data['job_id'],
                    'processing_time': 0.04  # Simulated processing time
                }
                
            except Exception as e:
                return {'success': False, 'job_id': job_data['job_id'], 'error': str(e)}
        
        # Execute concurrent job processing
        start_time = time.time()
        tasks = [process_single_job(job) for job in jobs]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Analyze results
        successful_jobs = [r for r in results if r['success']]
        failed_jobs = [r for r in results if not r['success']]
        
        total_time = end_time - start_time
        throughput = len(successful_jobs) / total_time
        
        print(f"\nConcurrent Job Processing Results:")
        print(f"  Total jobs: {len(results)}")
        print(f"  Successful: {len(successful_jobs)}")
        print(f"  Failed: {len(failed_jobs)}")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Throughput: {throughput:.2f} jobs/s")
        
        # Assertions
        assert len(successful_jobs) >= len(jobs) * 0.8  # 80% success rate
        assert throughput > 5  # At least 5 jobs per second


if __name__ == "__main__":
    pytest.main([__file__, "-v"])