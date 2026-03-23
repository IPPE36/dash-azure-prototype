# src/web/layouts/__init__.py

from .global_toast import build_global_toast
from .global_navbar import build_global_navbar, build_global_nav_offcanvas
from .jobs import build_layout_jobs
from .settings import build_input_list, build_dropdown, build_sliders

__all__ = [
    "build_global_navbar",
    "build_global_nav_offcanvas",
    "build_global_toast",
    "build_layout_jobs",
    "build_input_list",
    "build_dropdown",
    "build_sliders",
]
