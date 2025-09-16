"""
Unit tests for the Expiration Manager service.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from server.web.app.models import User, Paste
from server.web.app.services.expiration_manager import ExpirationManager

@pytest.mark.asyncio
async def test_cleanup_expired_pastes(db_session: AsyncSession):
    """
    Tests that the cleanup service correctly deactivates expired pastes.
    """
    async for session in db_session:
        manager = ExpirationManager(session)
        
        user = User(display_label="test_user")
        
        # Create a mix of pastes
        pastes = [
            Paste(paste_id="active", content="active", user_id=user.id),
            Paste(paste_id="expired", content="expired", user_id=user.id, expires_at=datetime.utcnow() - timedelta(days=1)),
            Paste(paste_id="not_expired", content="not_expired", user_id=user.id, expires_at=datetime.utcnow() + timedelta(days=1))
        ]
        user.content.extend(pastes)
        session.add(user)
        await session.commit()

        cleaned_count = await manager.cleanup_expired_pastes()
        
        assert cleaned_count == 1
        
        # Verify the state of each paste
        active_paste = await session.get(Paste, pastes[0].id)
        assert active_paste.is_active is True
        
        expired_paste = await session.get(Paste, pastes[1].id)
        assert expired_paste.is_active is False
        
        not_expired_paste = await session.get(Paste, pastes[2].id)
        assert not_expired_paste.is_active is True
        break
