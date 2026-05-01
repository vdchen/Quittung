from fastapi import APIRouter
from app.api.endpoints.v1 import exports, receipts

api_router = APIRouter()

# Include the sub-routers. 
api_router.include_router(exports.router)
api_router.include_router(receipts.router)