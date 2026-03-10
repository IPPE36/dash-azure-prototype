# src/web/app.py

import os
import redis

from flask_session import Session
import dash_bootstrap_components as dbc
from dash_extensions.enrich import dcc, html, DashProxy, TriggerTransform, MultiplexerTransform, page_container
from dash_breakpoints_new import WindowBreakpoints

from shared.db import init_db
from shared.logs import init_logs
from .auth import bp as auth_bp, request_guard
from .layouts import build_navbar, build_navbar_offcanvas
from .callbacks import register_callbacks_mobile, register_callbacks_navbar


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
    WindowBreakpoints(
        id="breakpoints",
        widthBreakpointThresholdsPx=[768, 1200],
        widthBreakpointNames=["mobile", "tablet", "desktop"],
    ),
    dcc.Location(id="app-location"),
    build_navbar(),
    build_navbar_offcanvas(),
    page_container,
])

register_callbacks_navbar()
register_callbacks_mobile()
