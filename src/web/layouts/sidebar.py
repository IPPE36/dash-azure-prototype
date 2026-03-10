# src/web/layout/sidebar.py

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html

from web.theme import (
    ICON_SETTINGS,
)


def build_sidebar_layout(
    *,
    content_main=None,
    content_sidebar=None,
    page_title="",
):

    content_sidebar = content_sidebar or []

    sidebar = dbc.Col(
        content_sidebar,
        xs=12,
        md=6,
        lg=4,
        id="sidebar",
        className="bg-light d-none d-md-block p-3 min-vh-100",
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
        md=6,
        lg=8,
        className="bg-light p-3 min-vh-100",
    )

    mobile_sidebar = dbc.Offcanvas(
        content_sidebar,
        id="mobile-offcanvas",
        title=[
            html.I(className=ICON_SETTINGS),
            f"{page_title}/Settings"
        ],        
        is_open=False,
        placement="start",
        className="d-md-none",
    )

    return html.Div(
        [
            mobile_sidebar,
            dbc.Row(
                [sidebar, main],
                className="g-0 bg-light min-vh-100",
            ),
        ],
        className="bg-light",
    )