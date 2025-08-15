# ----- Celery setup @src/workers/celery_app.py -----

from celery import Celery
from src.core.config import settings

celery_app=Celery(
    "hr_agent_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["src.workers.tasks"]
)

celery_app.conf.update(
    task_track_started=True
)