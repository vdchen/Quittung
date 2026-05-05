import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import pool
from alembic import context

# 1. Imports
from app.db.base import Base
from app.models.receipt import Receipt, LineItem
from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

target_metadata = Base.metadata
config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import logging

logger = logging.getLogger("alembic.runtime.migration")

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True
    )
    with context.begin_transaction():
        logger.info("Executing migration transaction...")
        context.run_migrations()
        logger.info("Migration committed!")

from app.db.utils import create_db_if_not_exists

async def run_async_migrations():
    # Ensure the database exists before trying to connect for migrations
    await create_db_if_not_exists(DATABASE_URL)

    connectable = create_async_engine(DATABASE_URL, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

# THE EXECUTION TRIGGER
if context.is_offline_mode():
    logger.info("Offline mode.")
else:
    run_migrations_online()