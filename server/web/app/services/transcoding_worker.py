"""
Background worker for processing video transcoding jobs.
"""
import asyncio
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from server.web.app.services.video_transcoding_service import VideoTranscodingService
from server.web.app.services.ffmpeg_service import FFmpegService
from server.web.app.services.video_s3_service import VideoS3Service
from server.web.app.services.hls_service import HLSService
from server.web.app.models import Video, TranscodingJob
from server.web.app.db import get_db_session

logger = logging.getLogger(__name__)

class TranscodingWorker:
    """Background worker for processing transcoding jobs."""
    
    def __init__(self, database_url: str, redis_url: str = "redis://localhost:6379",
                 s3_bucket: str = "meatlizard-video-storage", 
                 temp_dir: str = "/tmp/transcoding"):
        self.database_url = database_url
        self.redis_url = redis_url
        self.s3_bucket = s3_bucket
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        
        self.transcoding_service: Optional[VideoTranscodingService] = None
        self.ffmpeg_service = FFmpegService()
        self.s3_service: Optional[VideoS3Service] = None
        self.hls_service = HLSService(s3_bucket)
        self.running = False
        
        # Create async database engine
        self.engine = create_async_engine(database_url)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def start(self):
        """Start the worker."""
        self.running = True
        logger.info("Starting transcoding worker")
        
        # Initialize services
        async with self.async_session() as db:
            self.transcoding_service = VideoTranscodingService(db, self.redis_url)
            self.s3_service = VideoS3Service(self.s3_bucket)
        
        # Start worker loops
        await asyncio.gather(
            self._job_processor_loop(),
            self._retry_scheduler_loop(),
            self._cleanup_loop()
        )
    
    async def stop(self):
        """Stop the worker."""
        self.running = False
        logger.info("Stopping transcoding worker")
        
        if self.transcoding_service:
            await self.transcoding_service.close()
    
    async def _job_processor_loop(self):
        """Main job processing loop."""
        while self.running:
            try:
                async with self.async_session() as db:
                    transcoding_service = VideoTranscodingService(db, self.redis_url)
                    
                    # Get next job from queue
                    job_data = await transcoding_service.get_next_job()
                    
                    if job_data:
                        await self._process_job(job_data, transcoding_service)
                    else:
                        # No jobs available, wait a bit
                        await asyncio.sleep(5)
                        
            except Exception as e:
                logger.error(f"Error in job processor loop: {e}")
                await asyncio.sleep(10)
    
    async def _process_job(self, job_data: dict, transcoding_service: VideoTranscodingService):
        """Process a single transcoding job."""
        job_id = job_data["job_id"]
        video_id = job_data["video_id"]
        
        logger.info(f"Processing transcoding job {job_id} for video {video_id}")
        
        try:
            # Mark job as processing
            await transcoding_service.mark_job_processing(job_id)
            
            # Get video information
            async with self.async_session() as db:
                video = await db.get(Video, video_id)
                if not video:
                    raise Exception(f"Video {video_id} not found")
            
            # Download original video from S3
            temp_input_path = self.temp_dir / f"{job_id}_input.mp4"
            await self.s3_service.download_file(video.original_s3_key, str(temp_input_path))
            
            # Create temporary output paths
            temp_output_path = self.temp_dir / f"{job_id}_output.mp4"
            temp_hls_dir = self.temp_dir / f"{job_id}_hls"
            temp_hls_dir.mkdir(exist_ok=True)
            
            # Transcode video
            progress_reported = 0
            async for progress in self.ffmpeg_service.transcode_video(
                str(temp_input_path),
                str(temp_output_path),
                job_data["target_resolution"],
                job_data["target_framerate"],
                job_data["target_bitrate"]
            ):
                # Report progress every 10%
                if progress >= progress_reported + 10:
                    await transcoding_service.update_job_progress(job_id, progress // 2)  # First half is transcoding
                    progress_reported = progress
            
            # Validate transcoded output
            if not await self.ffmpeg_service.validate_output(str(temp_output_path)):
                raise Exception("Transcoded video validation failed")
            
            # Upload transcoded video to S3
            await transcoding_service.update_job_progress(job_id, 60)
            output_s3_key = f"transcoded/{video_id}/{job_data['quality_preset']}/video.mp4"
            await self.s3_service.upload_file(str(temp_output_path), output_s3_key)
            
            # Generate and upload HLS segments
            await transcoding_service.update_job_progress(job_id, 70)
            manifest_s3_key, segment_s3_keys = await self.hls_service.generate_hls_from_video(
                str(temp_output_path),
                video_id,
                job_data['quality_preset']
            )
            
            # Validate HLS segments
            await transcoding_service.update_job_progress(job_id, 90)
            if not await self.hls_service.validate_hls_segments(manifest_s3_key):
                raise Exception("HLS segment validation failed")
            
            # Get output file size
            output_file_size = await self.ffmpeg_service.get_file_size(str(temp_output_path))
            
            # Mark job as completed
            await transcoding_service.complete_job(
                job_id, output_s3_key, manifest_s3_key, output_file_size
            )
            
            logger.info(f"Successfully completed transcoding job {job_id}")
            
        except Exception as e:
            error_msg = f"Transcoding failed: {str(e)}"
            logger.error(f"Job {job_id} failed: {error_msg}")
            await transcoding_service.fail_job(job_id, error_msg, job_data)
            
        finally:
            # Clean up temporary files
            await self._cleanup_temp_files(job_id)
    
    async def _cleanup_temp_files(self, job_id: str):
        """Clean up temporary files for a job."""
        try:
            patterns = [
                f"{job_id}_input.*",
                f"{job_id}_output.*",
                f"{job_id}_hls"
            ]
            
            for pattern in patterns:
                for path in self.temp_dir.glob(pattern):
                    if path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        import shutil
                        shutil.rmtree(path)
                        
        except Exception as e:
            logger.warning(f"Failed to cleanup temp files for job {job_id}: {e}")
    
    async def _retry_scheduler_loop(self):
        """Loop to process scheduled retries."""
        while self.running:
            try:
                async with self.async_session() as db:
                    transcoding_service = VideoTranscodingService(db, self.redis_url)
                    await transcoding_service.process_scheduled_retries()
                    
            except Exception as e:
                logger.error(f"Error in retry scheduler loop: {e}")
            
            # Check for retries every 30 seconds
            await asyncio.sleep(30)
    
    async def _cleanup_loop(self):
        """Loop to clean up stale jobs."""
        while self.running:
            try:
                async with self.async_session() as db:
                    transcoding_service = VideoTranscodingService(db, self.redis_url)
                    await transcoding_service.cleanup_stale_jobs(timeout_minutes=60)
                    
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
            
            # Clean up every 10 minutes
            await asyncio.sleep(600)

async def main():
    """Main entry point for running the worker."""
    import os
    
    # Get configuration from environment
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    s3_bucket = os.getenv("S3_BUCKET_NAME", "meatlizard-video-storage")
    temp_dir = os.getenv("TRANSCODING_TEMP_DIR", "/tmp/transcoding")
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and start worker
    worker = TranscodingWorker(database_url, redis_url, s3_bucket, temp_dir)
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await worker.stop()

if __name__ == "__main__":
    asyncio.run(main())