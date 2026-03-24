# src/shared/db/__init__.py

from .core import configure_db
from .tasks import (
    add_task, 
    delete_task, 
    update_task, 
    get_task, 
    get_next_user_task_id, 
    get_queue_length, 
    get_queue_position, 
    get_user_task_rows, 
    get_user_task_count,
)
from .users import add_user, auth_dev_user, get_user_id, get_user_email

__all__ = [
    "configure_db",
    "add_task",
    "delete_task",
    "update_task",
    "get_task",
    "get_next_user_task_id",
    "get_queue_length",
    "get_queue_position",
    "get_user_task_rows",
    "get_user_task_count",
    "add_user",
    "auth_dev_user",
    "get_user_id",
    "get_user_email",
]
