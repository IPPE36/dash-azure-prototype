# src/web/callbacks/__init__.py

from .global_navbar import register_callbacks_navbar
from .global_toast import register_callbacks_toast, toast_close_payload, toast_payload

__all__ = [
    "register_callbacks_navbar",
    "register_callbacks_toast",
    "toast_close_payload",
    "toast_payload",
]
