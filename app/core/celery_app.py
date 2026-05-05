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

# Expire task results after 1 hour to prevent Redis memory accumulation.
celery_app.conf.result_expires = 3600

# Serializer settings for safety and consistency
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]

celery_app.conf.beat_schedule = {
    "cleanup-uploads-every-hour": {
        "task": "app.tasks.worker.cleanup_uploads_task",
        "schedule": 3600.0,  # every hour
    },
}