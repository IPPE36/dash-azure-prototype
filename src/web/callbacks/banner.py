# src/web/callbacks/background.py

import dash_bootstrap_components as dbc
from dash_extensions.enrich import html, Input, Output, callback, page_registry

from web.auth import get_user_name
from web.theme import ICON_PAGE_HOME, ICON_PAGE_APP


def register_callbacks_banner(dash_app) -> None:
        
    @dash_app.callback(
        Output("topbar-nav-menu", "children"),
        Output("topbar-user-menu", "label"),
        Output("topbar-nav-menu", "label"),
        Input("app-location", "pathname"),
    )
    def sync_top_banner(pathname: str | None):
        normalized_path = pathname or "/"
        nav_items = []
        for page in page_registry.values():
            page_path = str(page.get("path") or "")
            page_name = str(page.get("name") or page.get("title"))
            icon = ICON_PAGE_HOME if page_name == "Home" else ICON_PAGE_APP
            if page_path:
                nav_items.append(
                    dbc.DropdownMenuItem(
                        [
                            html.I(className=icon),
                            html.Span(page_name),
                        ],
                        href=page_path,
                        active=(page_path == normalized_path),
                    )
                )
            if page.get("path") == normalized_path:
                page_title = str(page.get("name") or page.get("title"))
        user_name = get_user_name() or "Account"
        return nav_items, user_name, page_title