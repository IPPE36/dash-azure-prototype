# src/shared/celery_app.py

import os
import logging
from celery import Celery
from celery.signals import worker_process_init
from dash import CeleryManager
from shared.db import init_db
from shared.logs import init_logs

init_logs()
init_db()
logger = logging.getLogger(__name__)

BROKER_URL = os.getenv("CELERY_BROKER_URL")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")

celery_app = Celery(
    "dash_azure_prototype",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["shared.tasks"],
)


# TLS: rediss:// or amqps://
# Non-TLS: redis:// or amqp://
# if BROKER_URL and BROKER_URL.startswith(("rediss://", "amqps://")):
#   celery_app.conf.broker_use_ssl = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

# Timeout
celery_app.conf.broker_connection_timeout = 5 
celery_app.conf.broker_transport_options = {
    "socket_connect_timeout": 5,
    "socket_timeout": 5,
}

# Azure/App Service: broker may not be ready instantly
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.broker_connection_max_retries = None

bg_manager = CeleryManager(celery_app)

@worker_process_init.connect
def warm_models(**_kwargs):
    # Runs once per worker process so large models are reused by tasks.
    logger.info("warming model runtime for worker process")
    from worker.model_runtime import warm_up
    warm_up()
    logger.info("model runtime warm-up complete")


if __name__ == "__main__":
    exit()
