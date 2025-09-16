import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import UploadFile
import os
from io import BytesIO

from server.web.app.services.media_upload_service import MediaUploadService
from server.web.app.services.storage_quota_manager import StorageQuotaManager
from server.web.app.services.file_validator import FileValidator
from server.web.app.services.ai_media_service import AIMediaService
from server.web.app.models import User

@pytest.mark.asyncio
async def test_upload_file(tmp_path):
    """
    Test the upload_file method of the MediaUploadService.
    """
    # Arrange
    db_session_mock = AsyncMock(spec=AsyncSession)
    quota_manager_mock = AsyncMock(spec=StorageQuotaManager)
    file_validator_mock = MagicMock(spec=FileValidator)
    ai_media_service_mock = AsyncMock(spec=AIMediaService)
    
    storage_path = tmp_path / "media"
    storage_path.mkdir()

    media_upload_service = MediaUploadService(
        db=db_session_mock,
        quota_manager=quota_manager_mock,
        file_validator=file_validator_mock,
        ai_media_service=ai_media_service_mock,
        storage_path=str(storage_path)
    )

    # Mock a file
    file_content = b"test content"
    upload_file = MagicMock(spec=UploadFile)
    upload_file.filename = "test.mp4"
    upload_file.file = BytesIO(file_content)
    upload_file.content_type = "video/mp4"
    upload_file.size = len(file_content)
    upload_file.read = AsyncMock(return_value=file_content)

    user = User(display_label="upload_user")

    # Mock the quota manager to allow the upload
    quota_manager_mock.has_sufficient_storage.return_value = True

    # Act
    with patch('server.web.app.services.media_upload_service.transcode_media_file.delay') as mock_delay:
        media_file = await media_upload_service.upload_file(upload_file, user)
        mock_delay.assert_called_once()

    # Assert
    file_validator_mock.validate.assert_called_once_with(upload_file)
    quota_manager_mock.has_sufficient_storage.assert_called_once()
    
    assert media_file.original_filename == "test.mp4"
    assert media_file.file_size_bytes == len(file_content)
    assert media_file.mime_type == "video/mp4"
    assert os.path.exists(media_file.storage_path)

    # Clean up the created file
    os.remove(media_file.storage_path)