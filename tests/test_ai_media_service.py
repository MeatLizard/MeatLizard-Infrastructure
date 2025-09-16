
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
import os
import shutil

from server.web.app.services.ai_media_service import AIMediaService
from server.web.app.models import MediaFile, User

@pytest.mark.asyncio
async def test_generate_captions(db_session: AsyncSession, tmp_path):
    """
    Test the generate_captions method of the AIMediaService.
    """
    async for session in db_session:
        # Arrange
        # Copy the test video to a temporary location
        test_video_path = "test_media/test_720p.mp4"
        temp_video_path = tmp_path / "test_720p.mp4"
        shutil.copy(test_video_path, temp_video_path)

        user = User(display_label="caption_user")
        media_file = MediaFile(
            media_id="caption-test",
            original_filename="test_720p.mp4",
            file_size_bytes=os.path.getsize(temp_video_path),
            mime_type="video/mp4",
            storage_path=str(temp_video_path),
            user=user
        )
        session.add(media_file)
        await session.commit()

        ai_media_service = AIMediaService()

        # Act
        captions = ai_media_service.generate_captions(media_file)

        # Assert
        assert captions is not None
        assert isinstance(captions, str)
