# src/shared/celery_app.py

import os
import logging

from celery import Celery
from celery.signals import worker_process_init
from dash import CeleryManager

from shared.logs import log_execution


_BROKER_URL = os.getenv("CELERY_BROKER_URL")
_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")

logger = logging.getLogger(__name__)

celery_app = Celery(
    "celery_app",
    broker=_BROKER_URL,
    backend=_RESULT_BACKEND,
    include=["shared.tasks"],
)

celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.broker_connection_max_retries = None
celery_app.conf.broker_connection_timeout = 5 
celery_app.conf.broker_transport_options = {
    "socket_connect_timeout": 5,
    "socket_timeout": 5,
}

bg_manager = CeleryManager(celery_app)

@worker_process_init.connect
@log_execution(logger_name=__name__)
def warm_models(**_kwargs):
    # Runs once per worker process so large models are reused by tasks.
    logger.info("warming model runtime for worker process")
    from worker.model_runtime import warm_up
    warm_up()
    logger.info("model runtime warm-up complete")


if __name__ == "__main__":
    exit()
