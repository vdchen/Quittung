from fastapi import FastAPI
from app.api.endpoints.v1.api import api_router
from app.core.config import settings

def get_application() -> FastAPI:
    """
    Factory pattern to initialize the FastAPI application.
    """
    _app = FastAPI(title=settings.PROJECT_NAME)

    _app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return _app

app = get_application()

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "online", "message": "Quittung API is running"}

@app.get("/", tags=["System"])
async def root():
    return {"status": "Quittung API is online"}