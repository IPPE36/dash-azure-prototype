import pytest
from flask import Flask

from web import auth as auth_mod


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["SERVER_NAME"] = "example.com"
    app.register_blueprint(auth_mod.bp)
    return app


def test_extract_user_name_and_email():
    user = {
        "preferred_username": "user@example.com",
        "name": "User Name",
        "email": "user@example.com",
    }
    assert auth_mod._extract_user_name(user) == "User Name"
    assert auth_mod._extract_user_email(user) == "user@example.com"


def test_extract_user_name_fallbacks():
    user = {"unique_name": "unique"}
    assert auth_mod._extract_user_name(user) == "unique"
    assert auth_mod._extract_user_email(user) == "unique"


def test_get_initials():
    assert auth_mod.get_initials(None) == "U"
    assert auth_mod.get_initials("") == "U"
    assert auth_mod.get_initials("alice") == "AL"
    assert auth_mod.get_initials("Alice Smith") == "AS"
    assert auth_mod.get_initials("a.b-c_d") == "AD"


def test_is_public_path():
    assert auth_mod.is_public_path("/login") is True
    assert auth_mod.is_public_path("/assets/app.css") is True
    assert auth_mod.is_public_path("/private") is False


def test_get_scope_list_and_string(app):
    with app.app_context():
        app.config["SCOPE"] = ["scope1", " ", "scope2"]
        assert auth_mod._get_scope() == ["scope1", "scope2"]
        app.config["SCOPE"] = "scope3, scope4"
        assert auth_mod._get_scope() == ["scope3", "scope4"]
        app.config["SCOPE"] = ""
        assert auth_mod._get_scope() == []


def test_request_id_and_client_ip(app):
    with app.test_request_context(
        "/hello",
        headers={
            "X-Request-ID": "req-1",
            "X-Forwarded-For": "1.2.3.4, 5.6.7.8",
        },
        environ_base={"REMOTE_ADDR": "9.9.9.9"},
    ):
        assert auth_mod._request_id() == "req-1"
        assert auth_mod._client_ip() == "1.2.3.4"
        extra = auth_mod._log_extra()
        assert extra["request_id"] == "req-1"
        assert extra["trace_id"] == "req-1"
        assert extra["client_ip"] == "1.2.3.4"
        assert extra["path"] == "/hello"
        assert extra["method"] == "GET"


def test_redirect_uri_prefers_config(app):
    with app.app_context():
        app.config["REDIRECT_URI"] = " https://example.com/callback "
        assert auth_mod._redirect_uri() == "https://example.com/callback"


def test_redirect_uri_falls_back_to_url_for(app):
    with app.test_request_context("/"):
        app.config.pop("REDIRECT_URI", None)
        uri = auth_mod._redirect_uri()
        assert uri.endswith("/getAToken")


def test_auth_mode_helpers(app):
    with app.app_context():
        app.config["AUTH_MODE"] = "dev"
        assert auth_mod._auth_mode() == "dev"
        assert auth_mod._dev_auth_enabled() is True
        assert auth_mod._msal_auth_enabled() is False
        app.config["AUTH_MODE"] = "msal"
        assert auth_mod._dev_auth_enabled() is False
        assert auth_mod._msal_auth_enabled() is True


def test_is_configured(app):
    with app.app_context():
        app.config["CLIENT_ID"] = "id"
        app.config["CLIENT_SECRET"] = "secret"
        assert auth_mod._is_configured() is True
        app.config["CLIENT_SECRET"] = ""
        assert auth_mod._is_configured() is False
