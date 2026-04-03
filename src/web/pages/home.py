# src/web/pages/home.py

from dash_extensions.enrich import register_page

from web.callbacks import register_callbacks_home
from web.layouts import build_layout_home

register_page(__name__, path="/", title="Home")

layout = build_layout_home()

register_callbacks_home()
