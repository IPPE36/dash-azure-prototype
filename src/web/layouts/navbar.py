# src/web/layout/layout_banner.py

import os

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html

from web.theme import (
    ICON_PAGE_APP,
    ICON_USER_LOGOUT,
)

_APP_NAME = os.getenv("APP_NAME", "Suite")
_VERSION = os.getenv("APP_VERSION", "1.0")

def build_navbar():
    navbar = dbc.Navbar(
        dbc.Container(
            [
                dbc.NavbarBrand(
                    [
                        html.I(className=ICON_PAGE_APP),
                        html.Span(f"{_APP_NAME}-{_VERSION}", className="fw-semibold"),
                    ],
                    className="text-white d-flex align-items-center",
                ),
                dbc.Nav(
                    [
                        dbc.DropdownMenu(
                            id="topbar-nav-menu",
                            label="Navigation",
                            color="primary",
                            size="md",
                            className="topbar-nav-menu border border-white",
                            align_end=True,
                            children=[],
                        ),
                        dbc.DropdownMenu(
                            id="topbar-user-menu",
                            label="Account",
                            color="primary",
                            size="md",
                            className="topbar-user-menu border border-white",
                            align_end=True,
                            children=[
                                html.Div(
                                    dbc.Switch(
                                        id="topbar-expert-switch",
                                        label="Expertmode",
                                        value=False,
                                    ),
                                    className="px-3 py-2",
                                ),
                                dbc.DropdownMenuItem(divider=True),
                                dbc.DropdownMenuItem(
                                    [
                                        html.I(className=ICON_USER_LOGOUT),
                                        html.Span("Logout"),
                                    ],
                                    href="/logout",
                                    external_link=True,
                                ),
                            ],
                        ),
                    ],
                    className="ms-auto d-flex align-items-center gap-2",
                    navbar=True,
                ),
            ],
            fluid=True,
            className="py-2",
        ),
        color="primary",
        dark=True,
        className="border-bottom",
    )
    return navbar
