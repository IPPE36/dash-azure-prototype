# src/web/pages/jobs.py

from dash_extensions.enrich import register_page

from web.layouts import build_jobs_layout
from web.callbacks import register_callbacks_jobs

register_page(__name__, path="/jobs", title="Jobs")

layout = build_jobs_layout()

register_callbacks_jobs()

