# src/web/callbacks/navbar.py

from dash_extensions.enrich import callback, clientside_callback, Input, Output, State, page_registry

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
        Output("navbar-page-title", "children"),
        Input("app-location", "pathname"),
    )
    def cb_update_page_title(pathname):
        for page in page_registry.values():
            if page["path"] == pathname:
                return page.get("title", "")
        return ""
    
    clientside_callback(
        """
        function(n, is_open) {
            if (!n) {
                return window.dash_clientside.no_update;
            }
            return !is_open;
        }
        """,
        Output("nav-offcanvas", "is_open"),
        Input("open-nav-offcanvas", "n_clicks"),
        State("nav-offcanvas", "is_open"),
    )