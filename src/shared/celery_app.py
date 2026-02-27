# src/shared/celery_app.py

import os
from celery import Celery
from dash import CeleryManager

BROKER_URL = os.getenv("CELERY_BROKER_URL")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")

celery_app = Celery(
    "dash_azure_prototype",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["shared.tasks"],
)

# Only worker sets this env var
imports = os.getenv("CELERY_IMPORTS")
if imports:
    celery_app.conf.imports = tuple(x.strip() for x in imports.split(",") if x.strip())

if BROKER_URL.startswith(("rediss://", "amqps://")):
    celery_app.conf.broker_use_ssl = {
        "ssl_cert_reqs": None
    }

celery_app.conf.broker_connection_timeout = 5
celery_app.conf.broker_transport_options = {
    "socket_connect_timeout": 5,
    "socket_timeout": 5,
}

bg_manager = CeleryManager(celery_app)

# Azure/App Service: broker may not be ready instantly
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.broker_connection_max_retries = None


if __name__ == "__main__":
    exit()