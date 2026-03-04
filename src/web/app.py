# src/web/app.py

import os
import redis

from flask_session import Session
import dash_bootstrap_components as dbc
from dash import page_registry
from dash_extensions.enrich import Input, Output, callback, dcc, html, DashProxy, TriggerTransform, MultiplexerTransform, page_container

from shared.db import init_db
from shared.logs import init_logs
from .auth import bp as auth_bp, get_user_name, request_guard
from .layouts.layout_banner import build_top_banner
from .theme import ICON_PAGE_HOME, ICON_PAGE_APP


_APP_NAME = os.getenv("APP_NAME", "Suite")
_VERSION = os.getenv("APP_VERSION", "1.0")
_LOCAL_SERVER = os.getenv("LOCAL_SERVER", "true").lower() == "true"
_DEV = os.getenv("DEV", "true").lower() == "true"
_CLIENT_ID = os.getenv("CLIENT_ID", "").strip()
_CLIENT_SECRET = os.getenv("CLIENT_SECRET", "").strip()
_TENANT_ID = os.getenv("TENANT_ID", "common").strip()
_AUTHORITY = os.getenv("AUTHORITY", f"https://login.microsoftonline.com/{_TENANT_ID}").strip()
_SECRET = os.getenv("SECRET", "fallback-secret")
_SCOPE = [s.strip() for s in os.getenv("SCOPE", "User.Read").split(",") if s.strip()]
_CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")

if _DEV and not _LOCAL_SERVER:
    os.environ.pop("HTTP_PROXY", None)
    os.environ.pop("HTTPS_PROXY", None)

init_logs()
init_db()

app = DashProxy(
    name=__name__,
    title=f"{_APP_NAME}-{_VERSION}",
    update_title=f"{_APP_NAME}-{_VERSION}",
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    transforms=[TriggerTransform(), MultiplexerTransform()],
    use_pages=True,
    prevent_initial_callbacks=True,
    suppress_callback_exceptions=True,
    assets_ignore=r".*\.map$|.*\.txt$|.*\.md$",
)

server = app.server
server.secret_key = _SECRET
server.config.update(
    AUTH_MODE="dev" if _DEV else "azure",  # or 'databricks'
    CLIENT_ID=_CLIENT_ID,
    CLIENT_SECRET=_CLIENT_SECRET,
    AUTHORITY=_AUTHORITY,
    SCOPE=_SCOPE,
    SESSION_TYPE='redis',
    SESSION_REDIS=redis.from_url(_CELERY_BROKER_URL),
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
    SESSION_COOKIE_SECURE=not _DEV,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)
Session(server)

server.register_blueprint(auth_bp)
server.before_request(request_guard)


app.layout = html.Div([
    dcc.Location(id="app-location"),
    build_top_banner(),
    page_container,
])


@callback(
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
        page_name = str(page.get("name") or page.get("title") or page_path or "Page")
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
            page_title = str(page.get("name") or page.get("title") or f"{_APP_NAME}")
    user_name = get_user_name() or "Account"
    return nav_items, user_name, page_title


if __name__ == "__main__":
    if _DEV:
        if _LOCAL_SERVER:
            server.run(host='localhost', port=8601, debug=False)
        else:  # use certificate and key files
            context = ('D:\Cert\Export\cert.pem', 'D:\Cert\Export\server.key')
            server.run(host='0.0.0.0', port=8601, debug=False, ssl_context=context)
    else:
        if _LOCAL_SERVER:
            server.run(host='0.0.0.0', port=443, debug=False)
        else:  # use certificate and key files
            context = ('D:\Cert\Export\cert.pem', 'D:\Cert\Export\server.key')
            server.run(host='0.0.0.0', port=443, debug=False, ssl_context=context)
