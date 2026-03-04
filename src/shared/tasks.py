# src/shared/tasks.py

import os
import time
import logging

from .celery_app import celery_app
from .db.tasks import add_task, get_task_run, update_task, update_task_run


_VERSION = os.getenv("APP_VERSION", "1.0")

logger = logging.getLogger(__name__)


@celery_app.task(name="long_task")
def long_task(x: int, user_id: str | None = None, duration_s: int = 10):
    task = long_task.request
    log_ctx = {"task_id": task.id, "task_name": task.task}
    logger.info("long_task started", extra=log_ctx)
    db_row = get_task_run(task.id)
    if db_row is not None:
        db_task_id = db_row["task_id"]
        update_task(
            task_id=db_task_id,
            status="RUNNING",
            progress=1,
            task_name=task.task,
            user_id=user_id,
            version=f"v{_VERSION}",
            input_payload={"x": x, "duration_s": duration_s},
        )
    else:
        db_task_id = add_task(
            celery_task_id=task.id,
            task_name=task.task,
            input_payload={"x": x, "duration_s": duration_s},
            version=f"v{_VERSION}",
            user_id=user_id,
            status="RUNNING",
            progress=1,
        )
    # Import lazily so the web process does not initialize model runtime.
    try:
        # Simulate predictable runtime to test UI progress behavior.
        duration = max(0, int(duration_s))
        if duration > 0:
            for second in range(duration):
                time.sleep(1)
                if db_task_id is not None:
                    simulated_progress = min(95, int(((second + 1) / duration) * 95))
                    update_task(task_id=db_task_id, status="RUNNING", progress=simulated_progress)
        from worker.model_runtime import get_runtime

        runtime = get_runtime()
        result = runtime.predict(x)
        update_task_run(
            task_id=db_task_id,
            task_name=task.task,
            status="COMPLETED",
            progress=100,
            output_payload={"result": result},
        )
        logger.info("long_task completed", extra=log_ctx)
        return result
    except Exception as exc:
        update_task_run(
            task_id=db_task_id,
            task_name=task.task,
            status="ABORTED",
            error_payload={"error": str(exc), "type": exc.__class__.__name__},
        )
        logger.exception("long_task failed", extra=log_ctx)
        raise
