# src/web/layouts/__init__.py

from .global_toast import build_global_toast
from .global_navbar import build_global_navbar, build_global_nav_offcanvas
from .jobs import build_jobs_layout
from .settings import build_input_list, build_dropdown, build_sliders

__all__ = [
    "build_global_navbar",
    "build_global_nav_offcanvas",
    "build_global_toast",
    "build_jobs_layout",
    "build_input_list",
    "build_dropdown",
    "build_sliders",
]
