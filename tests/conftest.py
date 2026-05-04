import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.main import app
from app.db.session import get_db
from app.models.receipt import Base
from fastapi_limiter.depends import RateLimiter

# Use the pre-configured settings which already handles .env.test selection
TEST_DATABASE_URL = settings.DATABASE_URL

test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(
    test_engine, expire_on_commit=False, class_=AsyncSession
)


from app.db.utils import create_db_if_not_exists

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """Create all tables once before the test session; drop them after."""
    # Ensure the test database exists
    await create_db_if_not_exists(TEST_DATABASE_URL)
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize FastAPILimiter for tests
    import redis.asyncio as redis
    from fastapi_limiter import FastAPILimiter
    r = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(r)

    yield
    await r.close()
    # Removed drop_all to prevent accidental wiping of dev database


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional test session that always rolls back on teardown."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client wired to the test database session."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[RateLimiter] = lambda: None
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()