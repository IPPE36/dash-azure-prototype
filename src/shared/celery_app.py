# src/shared/celery_app.py
# Design note: Celery config is centralized here so web + workers share settings.
# Worker init hooks are used to warm models and set runtime config per process.
# This avoids per-task overhead and keeps concurrency predictable.

import logging

from celery import Celery
from celery.signals import worker_process_init
from kombu import Queue

from shared.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND


logger = logging.getLogger(__name__)

celery_app = Celery(
    __name__,
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
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
    task_default_queue="default",
    task_queues=[
        Queue("default"),
        Queue("background"),
    ],
    task_routes={
        "long_task": {"queue": "background"},
        "short_task": {"queue": "default"},
    },
)

@worker_process_init.connect
def warm_up_workers(**kwargs):
    # Runs once per worker process so large models are reused by tasks.
    from shared.log import configure_logs
    configure_logs()
    from worker.torch_utils.bootstrap import configure_torch
    configure_torch()
    from worker.runtime import configure_runtime
    configure_runtime()
