import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator

# Fetch from environment (configured in your docker-compose)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/quittung_db"
)

# 1. Create the engine
# echo=True is great for dev—it logs every SQL query to your terminal
engine = create_async_engine(DATABASE_URL, echo=True, future=True)

# 2. Create a session factory
async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 3. Dependency to get DB session in FastAPI endpoints


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
