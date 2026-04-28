import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator
from sqlalchemy.pool import NullPool

# Fetch from env
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/quittung_db"
)

# 1. Create the engine
# echo=True is great for dev—it logs every SQL query to your terminal
engine = create_async_engine(DATABASE_URL, echo=True, future=True, poolclass=NullPool)

# 2. Create a session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 3. Dependency to get DB session in FastAPI endpoints


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
