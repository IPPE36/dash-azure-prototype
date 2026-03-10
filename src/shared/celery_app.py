# src/shared/celery_app.py

import os
import logging

from celery import Celery
from celery.signals import worker_process_init


_BROKER_URL = os.getenv("CELERY_BROKER_URL")
_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")

logger = logging.getLogger(__name__)

celery_app = Celery(
    "celery_app",
    broker=_BROKER_URL,
    backend=_RESULT_BACKEND,
    include=["shared.celery_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=86400,  # 1 day
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=None,
    broker_connection_timeout=5,
    broker_transport_options={
        "visibility_timeout": 720,  # > max expected task runtime
        "socket_timeout": 5,
        "socket_connect_timeout": 5,
        "retry_on_timeout": True,
    },
    task_soft_time_limit=300,
    task_time_limit=360,
    worker_concurrency=1,
    worker_max_tasks_per_child=200,  # helps with leaks/stability
    worker_send_task_events=False,
    task_send_sent_event=False,
)

@worker_process_init.connect
def warm_models(**kwargs):
    # Runs once per worker process so large models are reused by tasks.
    logger.info("model runtime warm-up started")
    from worker.model_runtime import warm_up
    warm_up()
    logger.info("model runtime warm-up completed")


if __name__ == "__main__":
    exit()
