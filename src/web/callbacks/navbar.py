# src/web/callbacks/navbar.py

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html, Input, Output, State, page_registry

from web.auth import get_user_name
from web.theme import ICON_PAGE_HOME, ICON_PAGE_APP


def register_callbacks_navbar(dash_app) -> None:
        
    @dash_app.callback(
        Output("topbar-user-menu", "label"),
        Input("app-location", "pathname"),
    )
    def update_user_name(pathname: str | None):
        user_name = get_user_name() or "Account"
        return user_name


    @dash_app.callback(
        Output("nav-offcanvas", "is_open"),
        Input("open-nav-offcanvas", "n_clicks"),
        State("nav-offcanvas", "is_open"),
    )
    def toggle_offcanvas(n, is_open):
        if not n:
            raise PreventUpdate
        return not is_open


    @dash_app.callback(
        Output("navbar-page-title", "children"),
        Input("app-location", "pathname"),
    )
    def update_page_title(pathname):
        for page in page_registry.values():
            if page["path"] == pathname:
                return page.get("title", "")
        return ""