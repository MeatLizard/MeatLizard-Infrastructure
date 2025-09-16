from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import ffmpeg
import os
import logging

from server.web.app.models import MediaFile, TranscodingStatusEnum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TranscodingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def transcode_media(self, media_file: MediaFile):
        media_file.transcoding_status = TranscodingStatusEnum.processing
        self.db.add(media_file)
        await self.db.commit()

        input_path = media_file.storage_path
        output_path_720p = f"{os.path.splitext(input_path)[0]}_720p.mp4"
        output_path_480p = f"{os.path.splitext(input_path)[0]}_480p.mp4"

        try:
            # 720p version
            (
                ffmpeg
                .input(input_path)
                .output(output_path_720p, vf='scale=-1:720')
                .run(capture_stdout=True, capture_stderr=True)
            )

            # 480p version
            (
                ffmpeg
                .input(input_path)
                .output(output_path_480p, vf='scale=-1:480')
                .run(capture_stdout=True, capture_stderr=True)
            )

            transcoded_files = {
                "720p": output_path_720p,
                "480p": output_path_480p,
            }
            
            media_file.transcoded_files = transcoded_files
            media_file.transcoding_status = TranscodingStatusEnum.completed
        except ffmpeg.Error as e:
            logger.error(f"Transcoding failed for {input_path}: {e.stderr.decode()}")
            media_file.transcoding_status = TranscodingStatusEnum.failed
            media_file.transcoding_error = e.stderr.decode()
        except Exception as e:
            logger.error(f"An unexpected error occurred during transcoding for {input_path}: {e}")
            media_file.transcoding_status = TranscodingStatusEnum.failed
            media_file.transcoding_error = str(e)
        
        self.db.add(media_file)
        await self.db.commit()
