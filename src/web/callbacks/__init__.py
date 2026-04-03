# src/web/callbacks/__init__.py

from .global_navbar import register_callbacks_navbar
from .global_toast import register_callbacks_toast, toast_payload
from .home import register_callbacks_home
from .jobs import register_callbacks_jobs
from .predictions import register_callbacks_predictions

__all__ = [
    "register_callbacks_navbar",
    "register_callbacks_toast",
    "toast_payload",
    "register_callbacks_home",
    "register_callbacks_jobs",
    "register_callbacks_predictions",
]
