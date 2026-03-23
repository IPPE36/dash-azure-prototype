# src/web/pages/jobs.py

from dash_extensions.enrich import register_page

from web.layouts import build_layout_jobs
from web.callbacks import register_callbacks_jobs

register_page(__name__, path="/jobs", title="Jobs")

layout = build_layout_jobs()

register_callbacks_jobs()

