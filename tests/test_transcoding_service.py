
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
import os
import shutil

from server.web.app.services.transcoding_service import TranscodingService
from server.web.app.models import MediaFile, User

@pytest.mark.asyncio
async def test_transcode_media(db_session: AsyncSession, tmp_path):
    """
    Test the transcode_media method of the TranscodingService.
    """
    async for session in db_session:
        # Arrange
        # Copy the test video to a temporary location
        test_video_path = "test_media/test_720p.mp4"
        temp_video_path = tmp_path / "test_720p.mp4"
        shutil.copy(test_video_path, temp_video_path)

        user = User(display_label="transcode_user")
        media_file = MediaFile(
            media_id="transcode-test",
            original_filename="test_720p.mp4",
            file_size_bytes=os.path.getsize(temp_video_path),
            mime_type="video/mp4",
            storage_path=str(temp_video_path),
            user=user
        )
        session.add(media_file)
        await session.commit()

        transcoding_service = TranscodingService(session)

        # Act
        await transcoding_service.transcode_media(media_file)

        # Assert
        assert media_file.transcoding_status == "completed"
        assert "720p" in media_file.transcoded_files
        assert "480p" in media_file.transcoded_files
        
        output_path_720p = media_file.transcoded_files["720p"]
        output_path_480p = media_file.transcoded_files["480p"]

        assert os.path.exists(output_path_720p)
        assert os.path.exists(output_path_480p)

        # Clean up the created files
        os.remove(output_path_720p)
        os.remove(output_path_480p)
