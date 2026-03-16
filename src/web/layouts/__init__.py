# src/web/layouts/__init__.py

from .navbar import build_navbar, build_navbar_offcanvas
from .page_jobs import build_jobs_main
from .settings import build_settings_input_list, build_settings_dropdown, build_settings_slider_list

__all__ = [
    "build_navbar",
    "build_navbar_offcanvas",
    "build_jobs_main",
    "build_settings_input_list",
    "build_settings_dropdown",
    "build_settings_slider_list",
]
