# src/shared/tasks.py

import os
import time
import logging

from .celery_app import celery_app
from .db import add_task, update_task_run


_VERSION = os.getenv("APP_VERSION", "1.0")

logger = logging.getLogger(__name__)


@celery_app.task(name="long_task")
def long_task(x: int, user_id: str | None = None, duration_s: int = 10):
    task = long_task.request
    log_ctx = {"task_id": task.id, "task_name": task.task}
    logger.info("long_task started", extra=log_ctx)
    db_task_id = add_task(
        celery_task_id=task.id,
        task_name=task.task,
        input_payload={"x": x, "duration_s": duration_s},
        version=f"v{_VERSION}",
        user_id=user_id,
    )
    # Import lazily so the web process does not initialize model runtime.
    try:
        # Simulate predictable runtime to test UI progress behavior.
        time.sleep(max(0, int(duration_s)))
        from worker.model_runtime import get_runtime

        runtime = get_runtime()
        result = runtime.predict(x)
        update_task_run(task_id=db_task_id, task_name=task.task, status="SUCCESS", output_payload={"result": result})
        logger.info("long_task completed", extra=log_ctx)
        return result
    except Exception as exc:
        update_task_run(
            task_id=db_task_id,
            task_name=task.task,
            status="FAILED",
            error_payload={"error": str(exc), "type": exc.__class__.__name__},
        )
        logger.exception("long_task failed", extra=log_ctx)
        raise
