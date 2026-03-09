# src/web/layout/navbar.py

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
                html.Button(
                    dbc.NavbarBrand(
                        [
                            html.I(className=ICON_PAGE_APP),
                            html.Span(_APP_NAME, className="fw-semibold ms-2"),
                        ],
                        className="text-white d-flex align-items-center",
                    ),
                    id="open-nav-offcanvas",
                    n_clicks=0,
                    className="btn btn-link p-0 border-0 text-decoration-none",
                    style={"cursor": "pointer"},
                ),
                html.Span("/", className="mx-1 text-white-50"),
                html.Span(
                    id="navbar-page-title",
                    className="text-white ms-3 fw-semibold",
                ),
                dbc.Nav(
                    [
                        dbc.DropdownMenu(
                            id="topbar-user-menu",
                            label="Account",
                            color="primary",
                            size="md",
                            className="border border-white rounded-2",
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


def build_nav_offcanvas():
    return dbc.Offcanvas(
        [
            dbc.Nav(
                [
                    dbc.NavLink("Home", href="/", active="exact"),
                    dbc.NavLink("Jobs", href="/jobs", active="exact"),
                ],
                vertical=True,
                pills=True,
            ),
        ],
        id="nav-offcanvas",
        title="Navigation",
        is_open=False,
        placement="start",
    )