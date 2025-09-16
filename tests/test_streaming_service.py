import pytest
from sqlalchemy.ext.asyncio import AsyncSession
import time
from fastapi import HTTPException

from server.web.app.services.streaming_service import StreamingService
from server.web.app.models import MediaFile, User, PrivacyLevelEnum

@pytest.mark.asyncio
async def test_generate_and_validate_signed_url(db_session: AsyncSession):
    """
    Test that a signed URL can be generated and validated successfully.
    """
    async for session in db_session:
        # Arrange
        streaming_service = StreamingService(session)
        media_id = "test-media-id"

        # Act
        signed_url = streaming_service.generate_signed_url(media_id)
        parts = signed_url.split("?")
        params = dict(p.split("=") for p in parts[1].split("&"))

        # Assert
        streaming_service.validate_signed_url(media_id, params["expires"], params["signature"])

@pytest.mark.asyncio
async def test_validate_expired_signed_url(db_session: AsyncSession):
    """
    Test that an expired signed URL fails validation.
    """
    async for session in db_session:
        # Arrange
        streaming_service = StreamingService(session)
        media_id = "test-media-id"

        # Act
        signed_url = streaming_service.generate_signed_url(media_id, expires_in=-1)
        parts = signed_url.split("?")
        params = dict(p.split("=") for p in parts[1].split("&"))

        # Assert
        with pytest.raises(HTTPException) as exc_info:
            streaming_service.validate_signed_url(media_id, params["expires"], params["signature"])
        
        assert exc_info.value.status_code == 410

@pytest.mark.asyncio
async def test_validate_invalid_signature(db_session: AsyncSession):
    """
    Test that a signed URL with an invalid signature fails validation.
    """
    async for session in db_session:
        # Arrange
        streaming_service = StreamingService(session)
        media_id = "test-media-id"

        # Act
        signed_url = streaming_service.generate_signed_url(media_id)
        parts = signed_url.split("?")
        params = dict(p.split("=") for p in parts[1].split("&"))

        # Assert
        with pytest.raises(HTTPException) as exc_info:
            streaming_service.validate_signed_url(media_id, params["expires"], "invalid-signature")
        
        assert exc_info.value.status_code == 403