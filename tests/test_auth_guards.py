import pytest
from flask import Flask, session

from web import auth as auth_mod


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["SERVER_NAME"] = "example.com"
    app.register_blueprint(auth_mod.bp)
    return app


def test_login_required_redirects_when_unauthenticated(app, monkeypatch):
    monkeypatch.setattr(auth_mod, "_is_authenticated", lambda: False)

    @auth_mod.login_required
    def view():
        return "ok"

    with app.test_request_context("/private"):
        resp = view()
        assert resp.status_code == 302
        assert "/login" in resp.location
        assert "next=/private" in resp.location


def test_login_required_allows_when_authenticated(app, monkeypatch):
    monkeypatch.setattr(auth_mod, "_is_authenticated", lambda: True)

    @auth_mod.login_required
    def view():
        return "ok"

    with app.test_request_context("/private"):
        assert view() == "ok"


def test_request_guard_public_path(app, monkeypatch):
    monkeypatch.setattr(auth_mod, "is_public_path", lambda path: True)
    with app.test_request_context("/assets/app.css"):
        assert auth_mod.request_guard() is None


def test_request_guard_unsupported_auth_mode(app, monkeypatch):
    monkeypatch.setattr(auth_mod, "is_public_path", lambda path: False)
    monkeypatch.setattr(auth_mod, "_dev_auth_enabled", lambda: False)
    monkeypatch.setattr(auth_mod, "_msal_auth_enabled", lambda: False)
    monkeypatch.setattr(auth_mod, "_auth_mode", lambda: "weird")

    with app.test_request_context("/private"):
        resp, status = auth_mod.request_guard()
        assert status == 500
        assert "Unsupported AUTH_MODE" in resp


def test_request_guard_redirects_when_unauthenticated(app, monkeypatch):
    monkeypatch.setattr(auth_mod, "is_public_path", lambda path: False)
    monkeypatch.setattr(auth_mod, "_dev_auth_enabled", lambda: True)
    monkeypatch.setattr(auth_mod, "_msal_auth_enabled", lambda: False)
    monkeypatch.setattr(auth_mod, "_is_authenticated", lambda: False)

    with app.test_request_context("/private"):
        resp = auth_mod.request_guard()
        assert resp.status_code == 302
        assert "/login" in resp.location
        assert "next=/private" in resp.location


def test_request_guard_inactive_user_clears_session(app, monkeypatch):
    monkeypatch.setattr(auth_mod, "is_public_path", lambda path: False)
    monkeypatch.setattr(auth_mod, "_dev_auth_enabled", lambda: True)
    monkeypatch.setattr(auth_mod, "_msal_auth_enabled", lambda: False)
    monkeypatch.setattr(auth_mod, "_is_authenticated", lambda: True)
    monkeypatch.setattr(auth_mod, "is_user_active", lambda username: False)
    monkeypatch.setattr(auth_mod, "add_user", lambda *args, **kwargs: None)

    with app.test_request_context("/private"):
        session["user_name"] = "bob"
        resp = auth_mod.request_guard()
        assert resp.status_code == 302
        assert "/login" in resp.location
        assert "next=/private" in resp.location
        assert session.get("user_name") is None