import asyncpg
import logging
from sqlalchemy.engine.url import make_url

logger = logging.getLogger(__name__)

async def create_db_if_not_exists(database_url: str):
    """
    Connect to the default 'postgres' database and create the target database
    specified in database_url if it does not already exist.
    """
    url = make_url(database_url)
    db_name = url.database
    
    # Construct a connection string for the default 'postgres' database
    # asyncpg requires a slightly different format or we can just replace the db in the string
    user = url.username
    password = url.password
    host = url.host
    port = url.port or 5432
    
    # We use the raw asyncpg connection to avoid SQLAlchemy's overhead for this simple check
    try:
        conn = await asyncpg.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database="postgres"
        )
        
        # Check if database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        
        if not exists:
            logger.info(f"Database {db_name} does not exist. Creating...")
            # CREATE DATABASE cannot run inside a transaction block
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            logger.info(f"Database {db_name} created successfully.")
        else:
            logger.debug(f"Database {db_name} already exists.")
            
        await conn.close()
    except Exception as e:
        logger.error(f"Error checking/creating database {db_name}: {e}")
        # We don't necessarily want to crash here if it's just a connection issue to 'postgres',
        # but the subsequent migration will likely fail anyway.
        raise
