# src/web/layouts/__init__.py

from .global_toast import build_global_toast
from .global_navbar import build_global_navbar, build_global_nav_offcanvas
from .page_jobs import build_jobs_main
from .settings import build_settings_input_list, build_settings_dropdown, build_settings_slider_list

__all__ = [
    "build_global_navbar",
    "build_global_nav_offcanvas",
    "build_global_toast",
    "build_jobs_main",
    "build_settings_input_list",
    "build_settings_dropdown",
    "build_settings_slider_list",
]
