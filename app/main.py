from fastapi import FastAPI
import uvicorn
import os
from app.api.endpoints import receipts, exports
from fastapi.responses import FileResponse
from app.services.export_service import generate_expenses_report


app = FastAPI(title="Quittung API")

api_v1_prefix = os.getenv("API_V1_PREFIX","/api/v1")

# Mount routers
app.include_router(
    receipts.router, 
    prefix=f"{api_v1_prefix}/receipts", 
    tags=["Receipts"]
)
app.include_router(
    exports.router, 
    prefix=f"{api_v1_prefix}/exports", 
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
