# src/web/callbacks/__init__.py

from .navbar import register_callbacks_navbar
from .sidebar import register_callbacks_mobile

__all__ = [
    "register_callbacks_navbar",
    "register_callbacks_mobile",
]
