# src/web/layouts.py

from typing import Iterable

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html

from web.theme import (
    COLOR_LIGHT_GRAY,
    COLOR_MID_GRAY,
    COLOR_DARK_BLUE,
)


def build_sidebar_layout(
    *,
    page_title: str,
    content,
    nav_items: Iterable[tuple[str, str]],
    app_name: str = "Suite",
):
    """Returns banner + sidebar layout..."""
    panel_padding = "1rem"
    sidebar_links = [
        dbc.NavLink(label, href=href, active="exact")
        for label, href in nav_items
    ]
    banner = html.Div(
        dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Col(html.Div(app_name, className="fw-semibold text-white"), width="auto"),
                        dbc.Col(html.Span(page_title, className="text-white-50"), width="auto"),
                    ],
                    className="g-0 justify-content-between align-items-center",
                )
            ],
            fluid=True,
        ),
        className="border-bottom rounded-0",
        style={
            "backgroundColor": COLOR_DARK_BLUE,
            "borderColor": COLOR_MID_GRAY,
            "borderRadius": 0,
            "padding": panel_padding,
        },
    )
    sidebar = dbc.Col(
        [
            html.Div("Navigation", className="fw-semibold mb-2"),
            dbc.Nav(sidebar_links, vertical=True, pills=True, className="gap-1"),
        ],
        xs=12,
        md=4,
        lg=4,
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
        lg=8,
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
            "minHeight": 0,
            "overflow": "hidden",
            "backgroundColor": COLOR_LIGHT_GRAY,
        },
    )
    return html.Div(
        children=[banner, layout],
        style={
            "minHeight": "100vh",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "borderRadius": 0,
            "backgroundColor": COLOR_LIGHT_GRAY,
        },
    )
