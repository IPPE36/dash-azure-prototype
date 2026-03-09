# src/web/callbacks/navbar.py

from dash_extensions.enrich import callback, Input, Output, State, page_registry
from dash.exceptions import PreventUpdate

from web.auth import get_user_name


def register_callbacks_navbar() -> None:
        
    @callback(
        Output("navbar-user-btn", "children"),
        Input("app-location", "pathname"),
    )
    def cb_update_user_name(pathname: str | None):
        user_name = get_user_name() or "Account"
        return user_name


    @callback(
        Output("nav-offcanvas", "is_open"),
        Input("open-nav-offcanvas", "n_clicks"),
        State("nav-offcanvas", "is_open"),
    )
    def cb_toggle_nav_offcanvas(n, is_open):
        if not n:
            raise PreventUpdate
        return not is_open


    @callback(
        Output("navbar-page-title", "children"),
        Input("app-location", "pathname"),
    )
    def cb_update_page_title(pathname):
        for page in page_registry.values():
            if page["path"] == pathname:
                return page.get("title", "")
        return ""