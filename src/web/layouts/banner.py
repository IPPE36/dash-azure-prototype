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

def build_top_banner():
    banner = html.Div(
        dbc.Container(
            dbc.Row(
                [   
                    dbc.Col(
                        html.Div(
                            [
                                html.I(className=ICON_PAGE_APP),
                                html.Span(f"{_APP_NAME}-{_VERSION}", className="fw-semibold"),
                            ],
                            className="text-white d-flex align-items-center",
                        ),
                        width=8,
                    ),
                    dbc.Col(
                        html.Div(
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
                        ),
                        width=4,
                        className="d-flex justify-content-end",
                    ),
                ],
                className="g-0 align-items-center",
            ),
            fluid=True,
            className="py-2",
        ),
        className="bg-primary border-bottom",
    )
    return banner
