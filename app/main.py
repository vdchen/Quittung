import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from app.api.endpoints.v1.api import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

# Configure structured logging as early as possible so all subsequent
# module-level loggers (worker, services, etc.) inherit the config.
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Initialize infrastructure connections on startup; tear them down on shutdown.
    """
    logger.info("application_startup", environment=settings.ENVIRONMENT)

    r = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(r)

    yield

    logger.info("application_shutdown")
    await r.close()


def get_application() -> FastAPI:
    """
    Factory pattern to initialize the FastAPI application.
    """
    _app = FastAPI(
        title=settings.PROJECT_NAME,
        lifespan=lifespan,
        # Hide docs in production
        docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
        redoc_url=None if settings.ENVIRONMENT == "production" else "/redoc",
    )

    # CORS — must be registered before routers so it wraps all responses.
    # Origins are configured via CORS_ORIGINS in .env; set explicitly in production.
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return _app


app = get_application()


@app.get("/health", tags=["System"])
async def health_check():
    """
    Liveness + readiness probe.

    Checks both the PostgreSQL database and the Redis broker. Returns 200 only
    if all dependencies are reachable. Orchestrators (Kubernetes, Docker, etc.)
    can use this endpoint to determine whether to route traffic to this instance.
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from sqlalchemy.pool import NullPool

    health = {"status": "ok", "checks": {}}

    # --- Redis check ---
    try:
        r = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        await r.ping()
        await r.close()
        health["checks"]["redis"] = "ok"
    except Exception as exc:
        logger.error("health_check_redis_failed", error=str(exc))
        health["checks"]["redis"] = "error"
        health["status"] = "degraded"

    # --- Database check ---
    try:
        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        health["checks"]["database"] = "ok"
    except Exception as exc:
        logger.error("health_check_db_failed", error=str(exc))
        health["checks"]["database"] = "error"
        health["status"] = "degraded"

    return health


@app.get("/", tags=["System"])
async def root():
    return {"status": "Quittung API is online"}