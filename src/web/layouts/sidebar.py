# src/web/layout/layout_sidebar.py

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html

from web.theme import (
    COLOR_LIGHT_GRAY,
    COLOR_MID_GRAY,
)


def build_sidebar_layout(
    *,
    content_main=None,
    content_sidebar=None,
):
    panel_padding = "1rem"
    content_sidebar = content_sidebar or []

    sidebar = dbc.Col(
        content_sidebar,
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
                "Settings",
                color="secondary",
                size="md",
                id="mobile-open-offcanvas-btn",
                className="settings-btn d-md-none mb-3",
            ),
            content_main,
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
            html.H3("Settings", className="mb-3"),
            *content_sidebar,
        ],
        id="mobile-offcanvas",
        title="Settings",
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