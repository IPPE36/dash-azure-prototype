# src/shared/tasks.py

import logging
from .celery_app import celery_app
from .db import create_task_run, update_task_run

logger = logging.getLogger(__name__)


@celery_app.task(name="long_task")
def long_task(x: int):
    task = long_task.request
    log_ctx = {"task_id": task.id, "task_name": task.task}
    logger.info("long_task started", extra=log_ctx)
    create_task_run(task_id=task.id, task_name=task.task, input_value=x)
    # Import lazily so the web process does not initialize model runtime.
    try:
        from worker.model_runtime import get_runtime
        runtime = get_runtime()
        result = runtime.predict(x)
        update_task_run(task_id=task.id, status="SUCCESS", result_text=str(result))
        logger.info("long_task completed", extra=log_ctx)
        return result
    except Exception as exc:
        update_task_run(task_id=task.id, status="FAILED", error_text=str(exc))
        logger.exception("long_task failed", extra=log_ctx)
        raise
