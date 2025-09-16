import asyncio
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

from server.web.app.models import Base

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session() -> AsyncSession:
    """
    Provide a transactional in-memory database session for each test function.
    The database schema is created from scratch for each test.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback() # Ensure the session is rolled back

    await engine.dispose()

@pytest.fixture(scope="function")
async def override_get_db(db_session: AsyncSession):
    """
    Fixture to override the get_db dependency with a test session.
    """
    async for session in db_session:
        yield lambda: session
        break
