import os

import pytest

from shared.celery_app import celery_app


RUN_CELERY_TESTS = os.getenv("RUN_CELERY_TESTS", "").lower() in {"1", "true", "t", "yes", "y", "on"}


@pytest.mark.skipif(not RUN_CELERY_TESTS, reason="set RUN_CELERY_TESTS=1 to enable")
def test_celery_broker_connects():
    with celery_app.connection() as conn:
        conn.ensure_connection(max_retries=1)


@pytest.mark.skipif(not RUN_CELERY_TESTS, reason="set RUN_CELERY_TESTS=1 to enable")
def test_celery_worker_ping():
    responses = celery_app.control.ping(timeout=2)
    if not responses:
        pytest.skip("no celery workers responded to ping")
