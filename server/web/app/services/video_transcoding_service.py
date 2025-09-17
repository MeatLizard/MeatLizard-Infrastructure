"""
Video transcoding service with Redis-based job queue and worker system.
"""
import asyncio
import json
import logging
import subprocess
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from server.web.app.models import Video, TranscodingJob, TranscodingStatus, VideoStatus
from server.web.app.services.base_service import BaseService

logger = logging.getLogger(__name__)

class VideoTranscodingService(BaseService):
    """Service for managing video transcoding jobs and workers."""
    
    def __init__(self, db: AsyncSession, redis_url: str = "redis://localhost:6379"):
        self.db = db
        self.redis_url = redis_url
        self.redis_client = None
        self.job_queue_key = "transcoding:jobs"
        self.processing_key = "transcoding:processing"
        self.retry_queue_key = "transcoding:retry"
        self.max_retries = 3
        self.retry_delays = [60, 300, 900]  # 1min, 5min, 15min
        
    async def _get_redis_client(self) -> redis.Redis:
        """Get Redis client connection."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        return self.redis_client
    
    async def queue_transcoding_job(self, video_id: str, quality_preset: str, 
                                  target_resolution: str, target_framerate: int, 
                                  target_bitrate: int) -> TranscodingJob:
        """Queue a new transcoding job."""
        # Create transcoding job record
        job = TranscodingJob(
            video_id=video_id,
            quality_preset=quality_preset,
            target_resolution=target_resolution,
            target_framerate=target_framerate,
            target_bitrate=target_bitrate,
            status=TranscodingStatus.queued
        )
        
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        
        # Add job to Redis queue
        job_data = {
            "job_id": str(job.id),
            "video_id": video_id,
            "quality_preset": quality_preset,
            "target_resolution": target_resolution,
            "target_framerate": target_framerate,
            "target_bitrate": target_bitrate,
            "created_at": datetime.utcnow().isoformat(),
            "retry_count": 0
        }
        
        redis_client = await self._get_redis_client()
        await redis_client.lpush(self.job_queue_key, json.dumps(job_data))
        
        logger.info(f"Queued transcoding job {job.id} for video {video_id} with preset {quality_preset}")
        return job
    
    async def get_next_job(self) -> Optional[Dict[str, Any]]:
        """Get the next job from the queue."""
        redis_client = await self._get_redis_client()
        
        # Try to get job from retry queue first
        job_data = await redis_client.brpop(self.retry_queue_key, timeout=1)
        if not job_data:
            # Get job from main queue
            job_data = await redis_client.brpop(self.job_queue_key, timeout=5)
        
        if job_data:
            _, job_json = job_data
            job = json.loads(job_json)
            
            # Move job to processing set
            await redis_client.sadd(self.processing_key, job_json)
            
            return job
        
        return None
    
    async def mark_job_processing(self, job_id: str) -> bool:
        """Mark a job as processing."""
        try:
            result = await self.db.execute(
                update(TranscodingJob)
                .where(TranscodingJob.id == job_id)
                .values(
                    status=TranscodingStatus.processing,
                    started_at=datetime.utcnow(),
                    progress_percent=0
                )
            )
            await self.db.commit()
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as processing: {e}")
            return False
    
    async def update_job_progress(self, job_id: str, progress_percent: int) -> bool:
        """Update job progress."""
        try:
            result = await self.db.execute(
                update(TranscodingJob)
                .where(TranscodingJob.id == job_id)
                .values(progress_percent=min(100, max(0, progress_percent)))
            )
            await self.db.commit()
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update progress for job {job_id}: {e}")
            return False
    
    async def complete_job(self, job_id: str, output_s3_key: str, 
                          hls_manifest_s3_key: str, output_file_size: int) -> bool:
        """Mark a job as completed."""
        try:
            result = await self.db.execute(
                update(TranscodingJob)
                .where(TranscodingJob.id == job_id)
                .values(
                    status=TranscodingStatus.completed,
                    completed_at=datetime.utcnow(),
                    progress_percent=100,
                    output_s3_key=output_s3_key,
                    hls_manifest_s3_key=hls_manifest_s3_key,
                    output_file_size=output_file_size,
                    error_message=None
                )
            )
            await self.db.commit()
            
            # Remove from processing set
            redis_client = await self._get_redis_client()
            # Find and remove the job from processing set
            processing_jobs = await redis_client.smembers(self.processing_key)
            for job_json in processing_jobs:
                job_data = json.loads(job_json)
                if job_data["job_id"] == job_id:
                    await redis_client.srem(self.processing_key, job_json)
                    break
            
            logger.info(f"Completed transcoding job {job_id}")
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to complete job {job_id}: {e}")
            return False
    
    async def fail_job(self, job_id: str, error_message: str, 
                      job_data: Optional[Dict[str, Any]] = None) -> bool:
        """Mark a job as failed and handle retry logic."""
        try:
            if job_data:
                retry_count = job_data.get("retry_count", 0)
                
                if retry_count < self.max_retries:
                    # Schedule retry
                    return await self._schedule_retry(job_data, error_message)
            
            # Mark as permanently failed
            result = await self.db.execute(
                update(TranscodingJob)
                .where(TranscodingJob.id == job_id)
                .values(
                    status=TranscodingStatus.failed,
                    completed_at=datetime.utcnow(),
                    error_message=error_message
                )
            )
            await self.db.commit()
            
            # Remove from processing set
            redis_client = await self._get_redis_client()
            processing_jobs = await redis_client.smembers(self.processing_key)
            for job_json in processing_jobs:
                job = json.loads(job_json)
                if job["job_id"] == job_id:
                    await redis_client.srem(self.processing_key, job_json)
                    break
            
            logger.error(f"Failed transcoding job {job_id}: {error_message}")
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as failed: {e}")
            return False
    
    async def _schedule_retry(self, job_data: Dict[str, Any], error_message: str) -> bool:
        """Schedule a job for retry with exponential backoff."""
        try:
            retry_count = job_data.get("retry_count", 0)
            delay_seconds = self.retry_delays[min(retry_count, len(self.retry_delays) - 1)]
            
            # Update job data for retry
            job_data["retry_count"] = retry_count + 1
            job_data["last_error"] = error_message
            job_data["retry_at"] = (datetime.utcnow() + timedelta(seconds=delay_seconds)).isoformat()
            
            # Update database with retry info
            await self.db.execute(
                update(TranscodingJob)
                .where(TranscodingJob.id == job_data["job_id"])
                .values(
                    status=TranscodingStatus.queued,
                    error_message=f"Retry {retry_count + 1}/{self.max_retries}: {error_message}"
                )
            )
            await self.db.commit()
            
            # Schedule retry in Redis
            redis_client = await self._get_redis_client()
            await redis_client.zadd(
                "transcoding:scheduled_retries",
                {json.dumps(job_data): time.time() + delay_seconds}
            )
            
            # Remove from processing set
            processing_jobs = await redis_client.smembers(self.processing_key)
            for job_json in processing_jobs:
                job = json.loads(job_json)
                if job["job_id"] == job_data["job_id"]:
                    await redis_client.srem(self.processing_key, job_json)
                    break
            
            logger.info(f"Scheduled retry {retry_count + 1} for job {job_data['job_id']} in {delay_seconds} seconds")
            return True
        except Exception as e:
            logger.error(f"Failed to schedule retry for job {job_data.get('job_id')}: {e}")
            return False
    
    async def process_scheduled_retries(self):
        """Process jobs scheduled for retry."""
        try:
            redis_client = await self._get_redis_client()
            current_time = time.time()
            
            # Get jobs ready for retry
            ready_jobs = await redis_client.zrangebyscore(
                "transcoding:scheduled_retries", 
                0, 
                current_time,
                withscores=False
            )
            
            for job_json in ready_jobs:
                # Move to retry queue
                await redis_client.lpush(self.retry_queue_key, job_json)
                # Remove from scheduled retries
                await redis_client.zrem("transcoding:scheduled_retries", job_json)
                
                job_data = json.loads(job_json)
                logger.info(f"Moved job {job_data['job_id']} to retry queue")
                
        except Exception as e:
            logger.error(f"Error processing scheduled retries: {e}")
    
    async def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        try:
            redis_client = await self._get_redis_client()
            
            stats = {
                "queued": await redis_client.llen(self.job_queue_key),
                "processing": await redis_client.scard(self.processing_key),
                "retry_queue": await redis_client.llen(self.retry_queue_key),
                "scheduled_retries": await redis_client.zcard("transcoding:scheduled_retries")
            }
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {"queued": 0, "processing": 0, "retry_queue": 0, "scheduled_retries": 0}
    
    async def cleanup_stale_jobs(self, timeout_minutes: int = 60):
        """Clean up jobs that have been processing too long."""
        try:
            redis_client = await self._get_redis_client()
            processing_jobs = await redis_client.smembers(self.processing_key)
            
            for job_json in processing_jobs:
                job_data = json.loads(job_json)
                
                # Check if job has been processing too long
                if "started_processing_at" in job_data:
                    started_at = datetime.fromisoformat(job_data["started_processing_at"])
                    if datetime.utcnow() - started_at > timedelta(minutes=timeout_minutes):
                        # Mark as failed due to timeout
                        await self.fail_job(
                            job_data["job_id"],
                            f"Job timed out after {timeout_minutes} minutes",
                            job_data
                        )
                        logger.warning(f"Cleaned up stale job {job_data['job_id']}")
                        
        except Exception as e:
            logger.error(f"Error cleaning up stale jobs: {e}")
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()