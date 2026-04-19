import os
from celery import Celery

celery_app = Celery(
    "worker",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=["app.worker"],
)

celery_app.conf.task_routes = {
    #"app.worker.process_receipt_task": "main-queue",
}