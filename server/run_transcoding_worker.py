#!/usr/bin/env python3
"""
Script to run the transcoding worker.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from server.web.app.services.transcoding_worker import TranscodingWorker

async def main():
    """Main entry point for the transcoding worker."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/var/log/transcoding_worker.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting transcoding worker")
    
    # Get configuration from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is required")
        sys.exit(1)
    
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    s3_bucket = os.getenv("S3_BUCKET_NAME", "meatlizard-video-storage")
    temp_dir = os.getenv("TRANSCODING_TEMP_DIR", "/tmp/transcoding")
    
    logger.info(f"Configuration:")
    logger.info(f"  Database URL: {database_url}")
    logger.info(f"  Redis URL: {redis_url}")
    logger.info(f"  S3 Bucket: {s3_bucket}")
    logger.info(f"  Temp Directory: {temp_dir}")
    
    # Create and start worker
    worker = TranscodingWorker(database_url, redis_url, s3_bucket, temp_dir)
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Worker failed with error: {e}")
        raise
    finally:
        await worker.stop()
        logger.info("Transcoding worker stopped")

if __name__ == "__main__":
    asyncio.run(main())