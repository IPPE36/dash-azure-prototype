import importlib

import pytest

from shared import env as env_mod


def test_env_str_strips_inline_comment(monkeypatch):
    monkeypatch.setenv("EXAMPLE", "dev  # note")
    assert env_mod.env_str("EXAMPLE") == "dev"


def test_env_str_trims_whitespace(monkeypatch):
    monkeypatch.setenv("EXAMPLE", "  value  ")
    assert env_mod.env_str("EXAMPLE") == "value"


def test_env_bool_truthy_values(monkeypatch):
    truthy = ["1", "true", "t", "yes", "y", "on"]
    for value in truthy:
        monkeypatch.setenv("FLAG", value)
        assert env_mod.env_bool("FLAG") is True


@pytest.mark.parametrize("value", ["0", "false", "f", "no", "n", "off", "", "random"])
def test_env_bool_falsey_values(monkeypatch, value):
    monkeypatch.setenv("FLAG", value)
    assert env_mod.env_bool("FLAG") is False


def test_env_list_parses_and_filters(monkeypatch):
    monkeypatch.setenv("LIST", "a, b, , c,  ")
    assert env_mod.env_list("LIST") == ["a", "b", "c"]


def test_get_int_env_default_when_missing(monkeypatch):
    monkeypatch.delenv("COUNT", raising=False)
    assert env_mod.get_int_env("COUNT", default=5) == 5


def test_get_int_env_invalid_value_logs_and_defaults(monkeypatch, caplog):
    monkeypatch.setenv("COUNT", "not-a-number")
    caplog.set_level("WARNING")
    assert env_mod.get_int_env("COUNT", default=7) == 7
    assert any("invalid COUNT" in record.message for record in caplog.records)


def test_get_int_env_min_max_bounds(monkeypatch, caplog):
    caplog.set_level("WARNING")
    monkeypatch.setenv("COUNT", "1")
    assert env_mod.get_int_env("COUNT", default=7, amin=2) == 7
    monkeypatch.setenv("COUNT", "10")
    assert env_mod.get_int_env("COUNT", default=7, amax=9) == 7


def test_get_int_env_valid(monkeypatch):
    monkeypatch.setenv("COUNT", "3")
    assert env_mod.get_int_env("COUNT", default=7, amin=1, amax=5) == 3


def test_config_defaults(monkeypatch):
    monkeypatch.delenv("DESKTOP", raising=False)
    monkeypatch.delenv("APP_VERSION", raising=False)
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("LOG_FORMAT", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import shared.config as config

    importlib.reload(config)

    assert config.DESKTOP is True
    assert config.AUTH_MODE == "dev"
    assert config.CELERY_BROKER_URL == "redis://redis:6379/0"
    assert config.CELERY_RESULT_BACKEND == "redis://redis:6379/0"
    assert config.DATABASE_URL == ""