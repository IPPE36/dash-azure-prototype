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
        md=5,
        lg=3,
        id="sidebar",
        className="app-sidebar bg-light d-none d-md-block p-3",  # d-md-block shows it on large screens
    )

    main = dbc.Col(
        [
            content_main,
        ],
        xs=12,
        md=7,
        lg=9,
        className="app-main bg-light p-3 pt-0",
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
        className="d-md-none bg-light",
    )

    return html.Div(
        [
            mobile_sidebar,
            dbc.Row(
                [sidebar, main],
                className="app-main-row g-0 bg-light",
            ),
        ],
        className="bg-light",
    )


def build_main(*, tabs=[]):
    """
    Build a main-area nav with a settings button on the left and tab buttons on the right.
    tabs: list of dicts with keys: label, content
    """
    settings_button = dbc.Button(
        "Settings",
        id="mobile-open-offcanvas-btn",
        size="md",
        color="dark",
        className="settings-btn d-block d-md-none",  # d-md-none hides it on large screens
    )
    
    tab_buttons = []
    tab_panels = []
    for i, (label, content) in enumerate(tabs):
        tab_buttons.append(
            dbc.Button(
                label,
                id={
                    "type": "main-nav-btn",
                    "index": label,
                },
                className=f"{label.lower()}-btn",
                color="primary" if not i else "secondary",
                size="md",
            )
        )
        tab_panels.append(
            html.Div(
                content,
                id={
                    "type": "main-nav-panel",
                    "index": label,
                },
                hidden=False if not i else True,
            )
        )

    button_group = dbc.Row(
        dbc.InputGroup(dbc.ButtonGroup([settings_button] + tab_buttons)),
        className="main-nav mb-3", 
    )

    return html.Div([button_group] + tab_panels)
