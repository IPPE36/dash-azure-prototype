# src/web/auth.py

import os
import uuid
import functools
from collections.abc import Callable

from flask import Blueprint, request, session, current_app, has_request_context, redirect, render_template, url_for
import msal

from shared.db.users import add_user, auth_dev_user


_REDIRECT_PATH = os.getenv("REDIRECT_PATH", "/getAToken").strip()
_PUBLIC_PATH_PREFIXES = ("/login", "/logout", "/logoffCompleted", "/assets/", "/_dash-", "/_favicon.ico", "/static/")

bp = Blueprint("auth", __name__, url_prefix="")


def _auth_mode() -> str:
    return str(current_app.config.get("AUTH_MODE", "dev")).strip().lower()


def _dev_auth_enabled() -> bool:
    return _auth_mode() == "dev"


def _msal_auth_enabled() -> bool:
    return _auth_mode() == "azure"


def _databricks_auth_enabled() -> bool:
    return _auth_mode() == "databricks"


def _oidc_auth_enabled() -> bool:
    return _msal_auth_enabled() or _databricks_auth_enabled()


def _is_configured() -> bool:
    return bool(current_app.config.get("CLIENT_ID") and current_app.config.get("CLIENT_SECRET"))


def is_public_path(path: str) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in _PUBLIC_PATH_PREFIXES)


def _get_scope() -> list[str]:
    scope = current_app.config.get("SCOPE")
    if isinstance(scope, list) and scope:
        return [str(s) for s in scope if str(s).strip()]
    if isinstance(scope, str) and scope.strip():
        return [s.strip() for s in scope.split(",") if s.strip()]


def _build_msal_app(cache: msal.SerializableTokenCache | None = None) -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        current_app.config.get("CLIENT_ID", ""),
        authority=current_app.config.get("AUTHORITY", ""),
        client_credential=current_app.config.get("CLIENT_SECRET", ""),
        token_cache=cache,
    )


def _build_auth_url() -> str:
    return _build_msal_app().get_authorization_request_url(
        _get_scope(),
        state=str(uuid.uuid4()),
        redirect_uri=url_for("auth.auth_response", _external=True),
    )


def _extract_user_name(user: dict | None) -> str | None:
    if not user:
        return None
    for key in ("name", "preferred_username", "email", "upn", "unique_name"):
        value = user.get(key)
        if value:
            return str(value)
    return None


def _is_authenticated() -> bool:
    if _dev_auth_enabled():
        return bool(session.get("dev_authenticated"))
    if _oidc_auth_enabled():
        return bool(session.get("user_name"))
    return False


def get_user_name() -> str | None:
    if not has_request_context():
        return None
    if not _is_authenticated():
        return None
    return session.get("user_name")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if _dev_auth_enabled():
        if request.method == "GET":
            return render_template("dev_login.html", error=None)

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if auth_dev_user(username, password):
            add_user(username, exists_ok=True)
            session["dev_authenticated"] = True
            session["user_name"] = username
            target = request.args.get("next") or "/"
            if not target.startswith("/"):
                target = "/"
            return redirect(target)
        return render_template("dev_login.html", error="Invalid username or password."), 401

    if _oidc_auth_enabled():
        if not _is_configured():
            return "Auth configuration error: set CLIENT_ID and CLIENT_SECRET.", 500
        return redirect(_build_auth_url())
    return "Unsupported AUTH_MODE. Use 'dev', 'azure' or 'databricks'.", 500


@bp.route(_REDIRECT_PATH)
def auth_response():
    if _oidc_auth_enabled():
        if not _is_configured():
            return "Auth configuration error: set CLIENT_ID and CLIENT_SECRET.", 500
        code = request.args.get("code")
        if not code:
            return "Missing authorization code.", 400
        cache = msal.SerializableTokenCache()
        result = _build_msal_app(cache=cache).acquire_token_by_authorization_code(
            code,
            scopes=_get_scope(),
            redirect_uri=url_for("auth.auth_response", _external=True),
        )
        if "error" in result:
            return render_template("auth_error.html", result=result), 401
        user_name = _extract_user_name(result.get("id_token_claims")) or "unknown-user"
        add_user(user_name, password_hash="", exists_ok=True)
        session["user_name"] = user_name
        return redirect("/")
    return "Unsupported AUTH_MODE. Use 'dev', 'azure' or 'databricks'.", 500


@bp.route("/logout")
def logout():
    session.clear()
    if _dev_auth_enabled():
        return redirect(url_for("auth.login"))
    if _oidc_auth_enabled():
        return redirect(
            "https://login.microsoftonline.com/common/oauth2/v2.0/logout"
            f"?post_logout_redirect_uri={url_for('auth.logoffCompleted', _external=True)}"
        )
    return "Unsupported AUTH_MODE. Use 'dev', 'azure' or 'databricks'.", 500


@bp.route("/logoffCompleted")
def logoffCompleted():
    return render_template("logout.html"), 200


def login_required(view: Callable):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not _is_authenticated():
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)
    return wrapped_view


def request_guard():
    if is_public_path(request.path):
        return None
    if not (_dev_auth_enabled() or _oidc_auth_enabled()):
        return "Unsupported AUTH_MODE. Use 'dev', 'azure' or 'databricks'.", 500
    if not _is_authenticated():
        return redirect(url_for("auth.login", next=request.path))
    user_name = session.get("user_name")
    if user_name:
        add_user(str(user_name), password_hash="", exists_ok=True)
    return None
