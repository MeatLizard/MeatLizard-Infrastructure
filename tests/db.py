import os
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Set the database URL for tests before importing the app
DATABASE_URL = "sqlite+aiosqlite:///./test.db"



from server.web.app.db import Base, get_db
from server.web.app.main import app

engine = create_async_engine(DATABASE_URL, echo=True)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

async def create_db_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_db_tables():
    if os.path.exists("./test.db"):
        os.remove("./test.db")

@pytest_asyncio.fixture(scope="module")
async def setup_database():
    await create_db_tables()
    yield
    await drop_db_tables()

@pytest_asyncio.fixture(scope="function")
async def db_fixture(setup_database):
    async with TestingSessionLocal() as session:
        yield session
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()