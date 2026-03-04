# src/web/layouts.py

from typing import Iterable

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html


def build_sidebar_layout(
    *,
    page_title: str,
    content,
    nav_items: Iterable[tuple[str, str]],
    app_name: str = "Suite",
):
    """Return a banner + sidebar layout shell for subpages."""
    sidebar_links = [
        dbc.NavLink(label, href=href, active="exact", className="rounded")
        for label, href in nav_items
    ]

    banner = dbc.Navbar(
        dbc.Container(
            [
                dbc.NavbarBrand(app_name, className="fw-semibold"),
                html.Span(page_title, className="text-body-secondary"),
            ],
            fluid=True,
        ),
        color="light",
        dark=False,
        className="border-bottom",
    )

    layout = dbc.Row(
        [
            dbc.Col(
                [
                    html.Div("Navigation", className="fw-semibold mb-2"),
                    dbc.Nav(sidebar_links, vertical=True, pills=True, className="gap-1"),
                ],
                xs=12,
                md=3,
                lg=2,
                className="border-end bg-body-tertiary p-3",
            ),
            dbc.Col(
                [
                    html.H3(page_title, className="mb-3"),
                    content,
                ],
                xs=12,
                md=9,
                lg=10,
                className="p-4",
            ),
        ],
        className="g-0",
    )

    return html.Div([banner, layout], className="min-vh-100")
