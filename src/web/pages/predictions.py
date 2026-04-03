# src/web/pages/jobs.py

from dash_extensions.enrich import register_page

from web.layouts import build_layout_predictions
from web.callbacks import register_callbacks_predictions

register_page(__name__, path="/pred", title="Pred")

layout = build_layout_predictions()

register_callbacks_predictions()

