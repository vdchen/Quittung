import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import pool
from alembic import context

# 1. Imports
from app.db.base import Base
from app.models.receipt import Receipt, LineItem
from app.db.session import DATABASE_URL

target_metadata = Base.metadata
config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True
    )
    with context.begin_transaction():
        print("🚀 Executing migration transaction...")
        context.run_migrations()
        print("✅ Migration committed!")

async def run_async_migrations():
    # Force the internal Docker address, but keep the asyncpg driver
    docker_url = "postgresql+asyncpg://postgres:postgres@db:5432/quittung_db"
    connectable = create_async_engine(docker_url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

# THE EXECUTION TRIGGER
if context.is_offline_mode():
    print("Offline mode.")
else:
    run_migrations_online()