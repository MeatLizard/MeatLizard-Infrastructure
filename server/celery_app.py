
from celery import Celery
from shared_lib.config import get_config

settings = get_config()

celery_app = Celery(
    "worker",
    broker=settings.redis.url,
    backend=settings.redis.url,
    include=["server.background_worker"]
)

celery_app.conf.update(
    task_track_started=True,
)
