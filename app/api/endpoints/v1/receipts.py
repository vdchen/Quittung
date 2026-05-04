import os
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from celery.result import AsyncResult
from app.tasks.worker import process_receipt_task
from app.core.celery_app import celery_app
from app.api.deps import get_api_key
from fastapi_limiter.depends import RateLimiter


router = APIRouter(
    prefix="/receipts",
    tags=["Receipts"],
    dependencies=[Depends(get_api_key)]
)

# Ensure upload directory exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", status_code=202, dependencies=[Depends(RateLimiter(times=20, seconds=60))])
async def upload_receipt(file: UploadFile = File(...),
                         chat_id: int | None = Form(None) # Accept chat_id from the bot
                         ):
    # 1. Validation
    if file.content_type not in ["application/pdf", "image/jpeg", "image/png"]:
        raise HTTPException(status_code=400, detail="Invalid file type")

    # 2. Generate a secure, unique filename to prevent overwrites
    CONTENT_TYPE_MAP = {
        "application/pdf": "pdf",
        "image/jpeg": "jpg",
        "image/png": "png"
    }
    
    file_extension = CONTENT_TYPE_MAP[file.content_type]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # 3. Save file to disk securely
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # 4. Trigger Celery Task - Pass the PATH, not the bytes
    task = process_receipt_task.delay(file_path, file.content_type, chat_id)

    return {
        "task_id": task.id,
        "status": "Processing started in background"
    } 


@router.get("/upload/status/{task_id}")
async def get_task_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": task_result.status, # e.g., PENDING, SUCCESS, FAILURE
    }
    
    if task_result.status == "SUCCESS":
        # Return the receipt ID or data
        response["result"] = task_result.result 
    elif task_result.status == "FAILURE":
        response["error"] = str(task_result.info)
        
    return response