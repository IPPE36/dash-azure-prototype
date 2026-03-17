# src/shared/tasks.py

import time
import logging
import random

from .celery_app import celery_app
from .db.tasks import get_task, update_task


logger = logging.getLogger(__name__)


@celery_app.task(name="long_task", bind=True)
def long_task(self, x: int, *, task_id: int) -> None:
    log_ctx = {"task_id": self.request.id, "task_name": self.name}
    logger.info("long_task started", extra=log_ctx)

    current_task = get_task(task_id)
    if current_task is None:
        return None

    update_task(task_id, status="RUNNING")

    try:
        from worker.model_runtime import get_runtime
        runtime = get_runtime()
        result = runtime.predict(x)

        progress = 0
        while progress < 100:
            time.sleep(1)
            progress += 10
            update_task(task_id, status="RUNNING", progress=progress)

        payload_len = random.randint(10, 100)
        output_payload = [
            {
                "x": random.random(),
                "y": random.random(),
                "z": random.random(),
            }
            for _ in range(payload_len)
        ]

        update_task(
            task_id,
            status="COMPLETED",
            progress=progress,
            output_payload=output_payload,
        )
        logger.info("long_task completed", extra=log_ctx)
        return result

    except Exception as e:
        update_task(
            task_id=task_id,
            status="ABORTED",
            error_payload={"error": str(e), "type": e.__class__.__name__},
        )
        logger.exception("long_task failed", extra=log_ctx)
        raise


@celery_app.task(name="short_task", bind=True)
def short_task(self, x: int, *, task_id: int) -> None:
    log_ctx = {"task_id": self.request.id, "task_name": self.name}
    logger.info("short_task started", extra=log_ctx)

    current_task = get_task(task_id)
    if current_task is None:
        return None

    update_task(task_id, status="RUNNING")

    try:
        # Simulate quick work without the heavy model runtime.
        result = x + 1
        time.sleep(1)

        update_task(
            task_id,
            status="COMPLETED",
            progress=100,
            output_payload=[{"result": result}],
        )
        logger.info("short_task completed", extra=log_ctx)
        return result

    except Exception as e:
        update_task(
            task_id=task_id,
            status="ABORTED",
            error_payload={"error": str(e), "type": e.__class__.__name__},
        )
        logger.exception("short_task failed", extra=log_ctx)
        raise
