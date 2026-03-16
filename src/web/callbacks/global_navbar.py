# src/web/callbacks/navbar.py

import re

from dash_extensions.enrich import callback, clientside_callback, Input, Output, State, page_registry

from web.auth import get_user_name, get_user_email


def register_callbacks_navbar() -> None:

    def _initials_from_name(name: str | None) -> str:
        if not name:
            return "U"
        parts = [p for p in re.split(r"[\\s._-]+", name.strip()) if p]
        if not parts:
            return "U"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return f"{parts[0][0]}{parts[-1][0]}".upper()
        
    @callback(
        Output("navbar-user-btn", "children"),
        Output("navbar-user-name", "children"),
        Output("navbar-user-email", "children"),
        Input("app-location", "pathname"),
    )
    def cb_update_user_name(pathname: str | None):
        user_name = get_user_name()
        user_email = get_user_email()
        initials = _initials_from_name(user_name or user_email)
        display_name = user_name or "Unknown user"
        display_email = user_email or "—"
        return initials, display_name, display_email

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
