from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.worker"],
)

celery_app.conf.task_routes = {
    # "app.tasks.worker.process_receipt_task": "main-queue",
}

celery_app.conf.beat_schedule = {
    "cleanup-uploads-every-hour": {
        "task": "app.tasks.worker.cleanup_uploads_task",
        "schedule": 3600.0,  # every hour
    },
}