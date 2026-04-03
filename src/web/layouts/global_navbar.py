# src/web/layout/navbar.py

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html

from web.theme import ICON_APP, ICON_NAV
from web.config import APP_NAME

def build_global_navbar():
    navbar = dbc.Navbar(
        dbc.Container(
            [   
                dbc.Button(
                    dbc.NavbarBrand(
                        [
                            html.I(className=ICON_NAV),
                            html.Span(APP_NAME, className="fw-semibold ms-2"),
                        ],
                        className="text-white d-flex align-items-center",
                    ),
                    id="open-nav-offcanvas",
                    className="btn btn-link p-2 border-0 text-decoration-none",
                    style={"cursor": "pointer"},
                ),
                html.Span("/", className="mx-1 text-white-50 d-none d-md-inline"),
                html.Span(
                    id="navbar-page-title",
                    className="text-white ms-3 fw-semibold d-none d-md-inline",
                ),
                dbc.Nav(
                    [
                        dbc.Button(
                            "AC",
                            id="navbar-user-btn",
                            color="primary",
                            size="md",
                            className="user-initials-btn border border-white me-1",
                        ),
                        dbc.Popover(
                            [
                                dbc.PopoverHeader(
                                    [
                                        html.Div(
                                            id="navbar-user-name",
                                            className="fw-semibold",
                                        ),
                                        html.Div(
                                            id="navbar-user-email",
                                            className="small text-muted",
                                        ),
                                    ],
                                    className="mb-2",
                                ),
                                dbc.PopoverBody(
                                    [
                                        dbc.Switch(
                                            id="navbar-expert-switch",
                                            label="Expert",
                                            value=False,
                                            className="mb-2",
                                        ),
                                        dbc.Button(
                                            "Logout",
                                            href="/logout",
                                            external_link=True,
                                            color="light",
                                            size="sm",
                                            className="logout-btn w-100",
                                        ),
                                    ],
                                )
                            ],
                            id="navbar-user-popover",
                            target="navbar-user-btn",
                            trigger="click",
                            placement="bottom-end",
                        )
                    ],
                    className="ms-auto d-flex align-items-center gap-2",
                    navbar=True,
                ),
            ],
            fluid=True,
            className="py-2 navbar-inner",
        ),
        color="primary",
        className="app-navbar fixed-top border-bottom border-primary border-3",
        id="navbar",
    )
    return navbar


def build_global_nav_offcanvas():
    nav_links = [
        dbc.NavLink(
            "Home",
            href="/",
            active="exact",
            id={"type": "nav-offcanvas-link", "page": "home"},
        ),
        dbc.NavLink(
            "Jobs",
            href="/jobs",
            active="exact",
            id={"type": "nav-offcanvas-link", "page": "jobs"},
        ),
        dbc.NavLink(
            "Pred",
            href="/pred",
            active="exact",
            id={"type": "nav-offcanvas-link", "page": "pred"},
        ),
        dbc.NavLink(
            "Team",
            href="/team",
            active="exact",
            id={"type": "nav-offcanvas-link", "page": "team"},
        ),
    ]

    return dbc.Offcanvas(
        [
            dbc.Nav(
                nav_links,
                vertical=True,
                pills=True,
            ),
        ],
        id="nav-offcanvas",
        title=[
            html.I(className=ICON_NAV),
            f"{APP_NAME} / Navigation"
        ],
        is_open=False,
        placement="start",
        className="bg-light ps-2 py-1"
    )
