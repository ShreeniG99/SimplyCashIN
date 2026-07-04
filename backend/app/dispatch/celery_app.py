from celery import Celery

from app.config import settings

celery = Celery("simplycashin", broker=settings.redis_url)
celery.conf.update(
    task_default_queue="scin.dispatch",
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
)
