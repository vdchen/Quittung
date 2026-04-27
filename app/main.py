from fastapi import FastAPI
import uvicorn
from app.config import settings
from app.api.endpoints import receipts, exports


app = FastAPI(title=settings.PROJECT_NAME)

# Mount routers
app.include_router(
    receipts.router, 
    prefix=f"{settings.API_V1_PREFIX}/receipts", 
    tags=["Receipts"]
)
app.include_router(
    exports.router, 
    prefix=f"{settings.API_V1_PREFIX}/exports", 
    tags=["Exports"]
)

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "online", "message": "Quittung API is running"}

@app.get("/", tags=["System"])
async def root():
    return {"status": "Quittung API is online"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
