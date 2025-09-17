#!/usr/bin/env python3
"""
Import Job Worker for MeatLizard AI Platform

This worker processes media import jobs in the background.
Run this script separately from the main web server.
"""
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# Add the server directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from web.app.services.import_job_queue import ImportJobManager
from web.app.models import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ImportWorkerRunner:
    """Runner for the import job worker"""
    
    def __init__(self):
        self.job_manager = None
        self.db_engine = None
        self.db_session_factory = None
        self.running = False
        
        # Configuration from environment variables
        self.database_url = os.getenv('DATABASE_URL', 'postgresql+asyncpg://test:test@localhost:5432/test')
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.worker_concurrency = int(os.getenv('IMPORT_WORKER_CONCURRENCY', '3'))
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
    
    async def setup_database(self):
        """Setup database connection and session factory"""
        self.db_engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
        
        # Create tables if they don't exist
        async with self.db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Create session factory
        self.db_session_factory = sessionmaker(
            bind=self.db_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        logger.info("Database connection established")
    
    async def setup_job_manager(self):
        """Setup import job manager"""
        self.job_manager = ImportJobManager(
            db_session_factory=self.db_session_factory,
            redis_url=self.redis_url
        )
        
        logger.info("Import job manager configured")
    
    async def start(self):
        """Start the worker"""
        try:
            await self.setup_database()
            await self.setup_job_manager()
            
            logger.info("Starting import job worker...")
            self.running = True
            
            # Start job manager
            await self.job_manager.start()
            
            # Keep running until shutdown signal
            while self.running:
                await asyncio.sleep(1)
                
                # Check job manager status periodically
                if self.job_manager:
                    status = await self.job_manager.get_status()
                    if status.get('status') != 'running':
                        logger.warning("Job manager is not running, attempting restart...")
                        await self.job_manager.stop()
                        await self.job_manager.start()
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            logger.error(f"Error running worker: {str(e)}")
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Starting cleanup...")
        
        if self.job_manager:
            await self.job_manager.stop()
            logger.info("Job manager stopped")
        
        if self.db_engine:
            await self.db_engine.dispose()
            logger.info("Database connection closed")
        
        logger.info("Cleanup completed")

async def main():
    """Main entry point"""
    logger.info("Import Job Worker starting...")
    
    # Check for required dependencies
    try:
        import yt_dlp
        logger.info(f"yt-dlp version: {yt_dlp.version.__version__}")
    except ImportError:
        logger.error("yt-dlp is not installed. Please install it with: pip install yt-dlp")
        sys.exit(1)
    
    try:
        import redis
        logger.info("Redis client available")
    except ImportError:
        logger.error("Redis client is not installed. Please install it with: pip install redis")
        sys.exit(1)
    
    runner = ImportWorkerRunner()
    await runner.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)