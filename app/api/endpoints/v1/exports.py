import os
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import FileResponse
from celery.result import AsyncResult
from app.core.celery_app import celery_app
from app.tasks.worker import generate_export_task
from app.api.deps import get_api_key
from fastapi_limiter.depends import RateLimiter

router = APIRouter(
    prefix="/exports",
    tags=["Exports"],
    dependencies=[Depends(get_api_key)]
)

# Rate limiting : 20 requests per minute per user
@router.post("/", status_code=202, dependencies=[Depends(RateLimiter(times=20, seconds=60))])
async def trigger_export(chat_id: Optional[int] = None):
    """
    Initiates an Excel export task.
    """
    # Use .hex[:8] for a shorter, cleaner filename
    file_name = f"report_{uuid.uuid4().hex[:8]}.xlsx"
    
    task = generate_export_task.delay(file_name, chat_id)
    
    return {
        "task_id": task.id,
        "message": "Export started",
        "poll_url": f"/api/v1/exports/status/{task.id}"
    }

@router.get("/status/{task_id}")
async def get_export_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    
    # Logic to catch non-existent tasks (PENDING with no metadata)
    if task_result.state == 'PENDING' and task_result.info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Task not found or expired"
        )
    
    if task_result.state == 'SUCCESS':
        result_data = task_result.result
        if result_data and "file_path" in result_data:
            file_path = result_data.get("file_path")
            if os.path.exists(file_path):
                return FileResponse(
                    path=file_path, 
                    filename="your_expenses.xlsx",
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        return {"status": "SUCCESS", "message": "File generated but not found on disk."}
    
    if task_result.state == 'FAILURE':
        return {"status": "FAILED", "error": str(task_result.info)}
        
    return {"status": task_result.state}