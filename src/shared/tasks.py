# src/shared/tasks.py

import time
from .celery_app import celery_app


@celery_app.task(name="long_task")
def long_task(x: int):
    time.sleep(1)
    return f"processed click #{x}"