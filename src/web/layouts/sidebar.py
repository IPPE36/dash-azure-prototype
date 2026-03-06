# src/web/layout/layout_sidebar.py

from typing import Iterable

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html

from web.theme import (
    COLOR_LIGHT_GRAY,
    COLOR_MID_GRAY,
)


def build_sidebar_layout(
    *,
    page_title: str,
    content,
    content_sidebar = [],
    nav_items: Iterable[tuple[str, str]],
):
    """Returns a content layout with page title and main area."""
    panel_padding = "1rem"
    _ = nav_items
    sidebar = dbc.Col(
        [
            html.H3("Menu", className="mb-3"),
            content_sidebar,
        ],
        xs=12,
        md=4,
        lg=3,
        style={
            "backgroundColor": COLOR_MID_GRAY,
            "padding": panel_padding,
        },
    )
    main = dbc.Col(
        [
            html.H3(page_title, className="mb-3"),
            content,
        ],
        xs=12,
        md=8,
        lg=9,
        style={
            "backgroundColor": COLOR_LIGHT_GRAY,
            "padding": panel_padding,
        },
    )
    layout = dbc.Row(
        [sidebar, main],
        className="g-0",
        style={
            "flex": "1 1 auto",
            "minHeight": "100vh",
            "overflow": "hidden",
            "backgroundColor": COLOR_LIGHT_GRAY,
        },
    )
    return html.Div(
        children=[layout],
        style={
            "minHeight": "100vh",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "borderRadius": 0,
            "backgroundColor": COLOR_LIGHT_GRAY,
        },
    )
