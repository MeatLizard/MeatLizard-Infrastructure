"""
Import Job Queue Service for processing media import jobs in the background.
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models import ImportJob, ImportStatus
from .media_import_service import MediaImportService
from .base_service import BaseService

logger = logging.getLogger(__name__)

class ImportJobQueue(BaseService):
    """Service for managing import job queue processing"""
    
    def __init__(self, db: AsyncSession, redis_url: str = "redis://localhost:6379"):
        super().__init__(db)
        self.redis_client = redis.from_url(redis_url)
        self.queue_name = "import_jobs"
        self.processing_jobs: Dict[str, asyncio.Task] = {}
        self.media_import_service = MediaImportService(db)
        self._running = False
    
    async def start_worker(self):
        """Start the background worker to process import jobs"""
        self._running = True
        logger.info("Starting import job queue worker")
        
        while self._running:
            try:
                # Get next job from queue
                job_data = await self.redis_client.blpop(self.queue_name, timeout=5)
                
                if job_data:
                    _, job_id_bytes = job_data
                    job_id = job_id_bytes.decode('utf-8')
                    
                    # Process job in background
                    task = asyncio.create_task(self._process_job(job_id))
                    self.processing_jobs[job_id] = task
                    
                    # Clean up completed tasks
                    await self._cleanup_completed_tasks()
                
            except Exception as e:
                logger.error(f"Error in import job worker: {str(e)}")
                await asyncio.sleep(1)
    
    async def stop_worker(self):
        """Stop the background worker"""
        self._running = False
        
        # Wait for all processing jobs to complete
        if self.processing_jobs:
            logger.info(f"Waiting for {len(self.processing_jobs)} jobs to complete")
            await asyncio.gather(*self.processing_jobs.values(), return_exceptions=True)
        
        await self.redis_client.close()
        logger.info("Import job queue worker stopped")
    
    async def queue_job(self, job_id: str) -> bool:
        """Add a job to the processing queue"""
        try:
            await self.redis_client.rpush(self.queue_name, job_id)
            logger.info(f"Queued import job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to queue job {job_id}: {str(e)}")
            return False
    
    async def get_queue_length(self) -> int:
        """Get the current queue length"""
        try:
            return await self.redis_client.llen(self.queue_name)
        except Exception as e:
            logger.error(f"Failed to get queue length: {str(e)}")
            return 0
    
    async def get_processing_jobs(self) -> Dict[str, str]:
        """Get currently processing jobs"""
        result = {}
        for job_id, task in self.processing_jobs.items():
            if task.done():
                result[job_id] = "completed"
            else:
                result[job_id] = "processing"
        return result
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a processing job"""
        if job_id in self.processing_jobs:
            task = self.processing_jobs[job_id]
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled import job {job_id}")
                return True
        return False
    
    async def _process_job(self, job_id: str):
        """Process a single import job"""
        try:
            logger.info(f"Processing import job {job_id}")
            
            # Process the job using media import service
            success = await self.media_import_service.process_import_job(job_id)
            
            if success:
                logger.info(f"Successfully processed import job {job_id}")
            else:
                logger.error(f"Failed to process import job {job_id}")
                
        except asyncio.CancelledError:
            logger.info(f"Import job {job_id} was cancelled")
            # Update job status to failed
            await self._mark_job_cancelled(job_id)
            raise
        except Exception as e:
            logger.error(f"Error processing import job {job_id}: {str(e)}")
            # The media import service should handle status updates
        finally:
            # Remove from processing jobs
            if job_id in self.processing_jobs:
                del self.processing_jobs[job_id]
    
    async def _cleanup_completed_tasks(self):
        """Clean up completed tasks from processing jobs"""
        completed_jobs = [
            job_id for job_id, task in self.processing_jobs.items() 
            if task.done()
        ]
        
        for job_id in completed_jobs:
            del self.processing_jobs[job_id]
    
    async def _mark_job_cancelled(self, job_id: str):
        """Mark a job as cancelled in the database"""
        try:
            # Get the job
            result = await self.db.execute(
                select(ImportJob).where(ImportJob.id == job_id)
            )
            job = result.scalar_one_or_none()
            
            if job and job.status not in [ImportStatus.completed, ImportStatus.failed]:
                job.status = ImportStatus.failed
                job.error_message = "Job was cancelled"
                job.completed_at = datetime.utcnow()
                await self.db.commit()
                
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as cancelled: {str(e)}")

class ImportJobManager:
    """Manager class for handling import job queue operations"""
    
    def __init__(self, db_session_factory, redis_url: str = "redis://localhost:6379"):
        self.db_session_factory = db_session_factory
        self.redis_url = redis_url
        self.worker_task: Optional[asyncio.Task] = None
        self.job_queue: Optional[ImportJobQueue] = None
    
    async def start(self):
        """Start the import job manager"""
        async with self.db_session_factory() as db:
            self.job_queue = ImportJobQueue(db, self.redis_url)
            self.worker_task = asyncio.create_task(self.job_queue.start_worker())
            logger.info("Import job manager started")
    
    async def stop(self):
        """Stop the import job manager"""
        if self.job_queue:
            await self.job_queue.stop_worker()
        
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Import job manager stopped")
    
    async def queue_job(self, job_id: str) -> bool:
        """Queue a job for processing"""
        if self.job_queue:
            return await self.job_queue.queue_job(job_id)
        return False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get queue status information"""
        if not self.job_queue:
            return {"status": "not_running"}
        
        return {
            "status": "running",
            "queue_length": await self.job_queue.get_queue_length(),
            "processing_jobs": await self.job_queue.get_processing_jobs()
        }