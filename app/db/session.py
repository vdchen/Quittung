from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator
import sys
from app.core.config import settings

# 1. Create the engine
# echo is tied to DEBUG so SQL logs are visible in development but silent in production.
# We use NullPool in Celery workers to prevent "different loop" errors when asyncio.run() creates new loops.
is_worker = any("celery" in arg for arg in sys.argv)
engine_kwargs = {"echo": settings.DEBUG, "future": True}
if is_worker:
    engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

# 2. Create a session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# 3. FastAPI dependency — yields one session per request
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
