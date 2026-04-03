# src/web/layouts/__init__.py

from .global_toast import build_global_toast
from .global_navbar import build_global_navbar, build_global_nav_offcanvas
from .jobs import build_layout_jobs
from .home import build_layout_home
from .predictions import build_layout_predictions
from .settings import build_input_list, build_dropdown, build_sliders
from .carousel import MediaCarousel, CarouselItem

__all__ = [
    "build_global_navbar",
    "build_global_nav_offcanvas",
    "build_global_toast",
    "build_layout_jobs",
    "build_layout_home",
    "build_input_list",
    "build_dropdown",
    "build_sliders",
    "build_layout_predictions",
    "MediaCarousel",
    "CarouselItem",
]
