# src/web/app.py
# Design note: web runtime is intentionally thin. It initializes logging/DB once,
# Wires auth + session config, and defers heavy work to background workers.
# This keeps HTTP latency low while workers handle CPU-heavy or long tasks.
# DashProxy transforms enable multi-output callbacks and trigger-only callbacks

import redis
import logging

from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix
import dash_bootstrap_components as dbc
from dash_extensions.enrich import dcc, html, DashProxy, TriggerTransform, MultiplexerTransform, page_container
from dash_breakpoints_new import WindowBreakpoints

from shared.log import configure_logs
from .auth import bp as auth_bp, request_guard
from .layouts import build_global_toast, build_global_navbar, build_global_nav_offcanvas
from .callbacks import register_callbacks_navbar, register_callbacks_toast
from .config import (
    APP_NAME,
    APP_VERSION,
    AUTHORITY,
    CELERY_BROKER_URL,
    CLIENT_ID,
    CLIENT_SECRET,
    DESKTOP,
    REDIRECT_PATH,
    REDIRECT_URI,
    SCOPE,
    SECRET,
    AUTH_MODE,
)

custom_theme = "/assets/bootstrap.min.css"
app = DashProxy(
    name=__name__,
    title=f"{APP_NAME}-{APP_VERSION}",
    update_title=f"{APP_NAME}-{APP_VERSION}",
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME, custom_theme],
    transforms=[TriggerTransform(), MultiplexerTransform()],
    use_pages=True,
    prevent_initial_callbacks=True,
    suppress_callback_exceptions=True,
    assets_ignore=r".*\.map$|.*\.txt$|.*\.md$|bootstrap\.min\.css$",
)

server = app.server
server.secret_key = SECRET

# propagate flask logger to app logger
configure_logs()
for name in ("flask.app", "werkzeug"):
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.propagate = True

# ProxyFix respects X-Forwarded-* headers behind reverse proxies (e.g. Azure),
# so URL generation and scheme detection remain correct.
server.wsgi_app = ProxyFix(server.wsgi_app, x_proto=1, x_host=1)

_cookie_name = f"{APP_NAME}".strip().lower().replace(" ", "_") or "app"
_cookie_name = f"{_cookie_name}_session"

server.config.update(
    AUTH_MODE=AUTH_MODE,
    CLIENT_ID=CLIENT_ID,
    CLIENT_SECRET=CLIENT_SECRET,
    AUTHORITY=AUTHORITY,
    SCOPE=SCOPE,
    REDIRECT_URI=REDIRECT_URI,
    REDIRECT_PATH=REDIRECT_PATH,
    PREFERRED_URL_SCHEME="https",
    SESSION_TYPE="redis",
    SESSION_REDIS=redis.from_url(CELERY_BROKER_URL, decode_responses=False),
    SESSION_KEY_PREFIX="session:",
    SESSION_COOKIE_NAME=_cookie_name,
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
    SESSION_COOKIE_SECURE=not DESKTOP,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
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
    dcc.Store(id="toast-store"),
    build_global_navbar(),
    build_global_toast(),
    build_global_nav_offcanvas(),
    html.Div(page_container, className="app-content"),
])

register_callbacks_navbar()
register_callbacks_toast()
