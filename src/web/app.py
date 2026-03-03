# src/web/app.py

import os
from flask import send_from_directory
import redis

from flask_session import Session
import dash_bootstrap_components as dbc
from dash_extensions.enrich import html, dcc, DashProxy, page_container, TriggerTransform, MultiplexerTransform

from web.auth import bp as auth_bp, request_guard
from shared.celery_app import bg_manager
from shared.db import init_db
from shared.logs import init_logs


_VERSION = os.getenv("APP_VERSION", "1.0")
_LOCAL_SERVER = os.getenv("LOCAL_SERVER", "true").lower() == "true"
_DEV = os.getenv("DEV", "true").lower() == "true"
_CLIENT_ID = os.getenv("CLIENT_ID", "").strip()
_CLIENT_SECRET = os.getenv("CLIENT_SECRET", "").strip()
_TENANT_ID = os.getenv("TENANT_ID", "common").strip()
_AUTHORITY = os.getenv("AUTHORITY", f"https://login.microsoftonline.com/{_TENANT_ID}").strip()
_SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret")
_SCOPE = [s.strip() for s in os.getenv("SCOPE", "User.Read").split(",") if s.strip()]
_CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")

init_logs()
init_db()

app = DashProxy(
    name=__name__,
    title=f"Suite {_VERSION}",
    update_title=f"Suite {_VERSION}",
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    transforms=[TriggerTransform(), MultiplexerTransform()],
    use_pages=True,
    prevent_initial_callbacks=True,
    suppress_callback_exceptions=True,
    background_callback_manager=bg_manager,
)

server = app.server
server.secret_key = _SECRET_KEY
server.config.update(
    AUTH_MODE="dev" if _DEV else "entra",
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


@server.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(server.root_path, 'assets', 'webicon'),
        'favicon.ico', mimetype='image/vnd.microsoft.icon')


app.layout = html.Div([
    html.H2("Dash + Pages"),
    dcc.Link("Home", href="/"),
    html.Br(),
    dcc.Link("Jobs", href="/jobs"),
    html.Hr(),
    page_container,
])


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
