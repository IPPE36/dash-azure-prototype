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
    content,
    content_sidebar=None,
    nav_items=None,
):
    panel_padding = "1rem"
    content_sidebar = content_sidebar or []

    sidebar = dbc.Col(
        [
            html.H3("Menu", className="mb-3"),
            *content_sidebar,
        ],
        xs=12,
        md=4,
        lg=3,
        className="d-none d-md-block",
        style={
            "backgroundColor": COLOR_MID_GRAY,
            "padding": panel_padding,
            "minHeight": "100vh",
        },
    )

    main = dbc.Col(
        [
            dbc.Button(
                "Menu",
                id="open-sidebar-btn",
                className="d-md-none mb-3",
            ),
            content,
        ],
        xs=12,
        md=8,
        lg=9,
        style={
            "backgroundColor": COLOR_LIGHT_GRAY,
            "padding": panel_padding,
            "minHeight": "100vh",
        },
    )

    mobile_sidebar = dbc.Offcanvas(
        [
            html.H3("Menu", className="mb-3"),
            *content_sidebar,
        ],
        id="mobile-sidebar",
        title="Menu",
        is_open=False,
        placement="start",
        className="d-md-none",
    )

    return html.Div(
        [
            mobile_sidebar,
            dbc.Row(
                [sidebar, main],
                className="g-0",
                style={
                    "minHeight": "100vh",
                    "backgroundColor": COLOR_LIGHT_GRAY,
                },
            ),
        ],
        style={
            "minHeight": "100vh",
            "backgroundColor": COLOR_LIGHT_GRAY,
        },
    )