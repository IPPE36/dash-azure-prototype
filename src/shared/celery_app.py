# src/shared/celery_app.py
# Design note: Celery config is centralized here so web + workers share settings.
# Worker init hooks are used to warm models and set runtime config per process.
# This avoids per-task overhead and keeps concurrency predictable.

import logging

from kombu import Queue
from celery import Celery
from celery.signals import (
    worker_process_init,
    setup_logging,
    worker_ready,
    task_prerun,
    task_postrun,
    task_failure,
)

from shared.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
from .log import configure_logs, log_timed_block


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

@setup_logging.connect
def on_setup_logging(**kwargs):
    configure_logs()

@worker_process_init.connect
def warm_up_worker(**kwargs):
    with log_timed_block("configure runtime", logger=logger):
        from worker.runtime import configure_runtime
        configure_runtime()

    with log_timed_block("configure torch", logger=logger):
        from worker.torch_utils.bootstrap import configure_torch
        configure_torch()

@worker_ready.connect
def on_worker_ready(sender=None, **kwargs):
    logger.info("worker ready", extra={"hostname": sender})

@task_prerun.connect
def on_task_prerun(task_id=None, task=None, args=None, kwargs=None, **extra):
    logger.info(
        "task start | task=%s task_id=%s",
        getattr(task, "name", None),
        task_id,
        extra={"task_id": task_id, "task_name": getattr(task, "name", None)},
    )

@task_postrun.connect
def on_task_postrun(task_id=None, task=None, state=None, retval=None, **extra):
    logger.info(
        "task end | task=%s task_id=%s state=%s",
        getattr(task, "name", None),
        task_id,
        state,
        extra={"task_id": task_id, "task_name": getattr(task, "name", None)},
    )

@task_failure.connect
def on_task_failure(task_id=None, exception=None, args=None, kwargs=None, einfo=None, sender=None, **extra):
    logger.error(
        "task failed | task=%s task_id=%s error=%s",
        getattr(sender, "name", None),
        task_id,
        exception,
        extra={"task_id": task_id, "task_name": getattr(sender, "name", None)},
        exc_info=einfo.exc_info if einfo else None,
    )