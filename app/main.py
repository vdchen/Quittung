import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter
from app.api.endpoints.v1.api import api_router
from app.core.config import settings

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Initialize the FastAPILimiter on startup using the existing Redis instance.
    """
    r = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(r)
    yield
    await r.close()

def get_application() -> FastAPI:
    """
    Factory pattern to initialize the FastAPI application.
    """
    _app = FastAPI(
        title=settings.PROJECT_NAME,
        lifespan=lifespan
    )

    _app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return _app

app = get_application()

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "online", "message": "Quittung API is running"}

@app.get("/", tags=["System"])
async def root():
    return {"status": "Quittung API is online"}