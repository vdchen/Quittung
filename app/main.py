from fastapi import FastAPI
import uvicorn
from app.api.endpoints.v1.api import api_router
from app.config import settings


app = FastAPI(title=settings.PROJECT_NAME)

# Mount routers
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "online", "message": "Quittung API is running"}

@app.get("/", tags=["System"])
async def root():
    return {"status": "Quittung API is online"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
