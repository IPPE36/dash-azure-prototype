import json

from shared.db import core


def test_load_devusers_json_missing_file(monkeypatch, tmp_path, caplog):
    caplog.set_level("WARNING")
    missing = tmp_path / "missing.json"
    monkeypatch.setattr(core, "_DEV_USERS_PATH", missing)

    assert core._load_devusers_json() == []


def test_load_devusers_json_invalid_json(monkeypatch, tmp_path, caplog):
    caplog.set_level("WARNING")
    bad = tmp_path / "bad.json"
    bad.write_text("{not: valid}", encoding="utf-8")
    monkeypatch.setattr(core, "_DEV_USERS_PATH", bad)

    assert core._load_devusers_json() == []
    assert any("failed to read dev users json" in record.message for record in caplog.records)


def test_load_devusers_json_not_list(monkeypatch, tmp_path, caplog):
    caplog.set_level("WARNING")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"username": "a"}), encoding="utf-8")
    monkeypatch.setattr(core, "_DEV_USERS_PATH", bad)

    assert core._load_devusers_json() == []
    assert any("dev users json must be a list" in record.message for record in caplog.records)


def test_load_devusers_json_filters_and_normalizes(monkeypatch, tmp_path):
    payload = [
        {"username": "  alice  ", "password": "  secret  ", "role": "Admin", "email": "a@example.com", "is_active": True},
        {"username": "", "password": "x"},
        {"username": "bob", "password": ""},
        "not-a-dict",
        {"username": "carol", "password": "pw", "role": "", "email": None},
    ]
    path = tmp_path / "dev_users.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(core, "_DEV_USERS_PATH", path)

    users = core._load_devusers_json()

    assert users == [
        {
            "username": "alice",
            "password": "secret",
            "role": "Admin",
            "email": "a@example.com",
            "is_active": True,
        },
        {
            "username": "carol",
            "password": "pw",
            "role": "user",
            "email": None,
            "is_active": True,
        },
    ]


def test_load_devusers_json_boolean_coercion(monkeypatch, tmp_path):
    payload = [
        {"username": "eva", "password": "pw", "is_active": ""},
        {"username": "zoe", "password": "pw", "is_active": "yes"},
    ]
    path = tmp_path / "dev_users.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(core, "_DEV_USERS_PATH", path)

    users = core._load_devusers_json()

    assert users == [
        {
            "username": "eva",
            "password": "pw",
            "role": "user",
            "email": None,
            "is_active": False,
        },
        {
            "username": "zoe",
            "password": "pw",
            "role": "user",
            "email": None,
            "is_active": True,
        },
    ]


def test_load_devusers_json_allows_duplicates(monkeypatch, tmp_path):
    payload = [
        {"username": "dup", "password": "one"},
        {"username": "dup", "password": "two"},
    ]
    path = tmp_path / "dev_users.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(core, "_DEV_USERS_PATH", path)

    users = core._load_devusers_json()

    assert users == [
        {
            "username": "dup",
            "password": "one",
            "role": "user",
            "email": None,
            "is_active": True,
        },
        {
            "username": "dup",
            "password": "two",
            "role": "user",
            "email": None,
            "is_active": True,
        },
    ]


def test_load_devusers_json_email_normalization(monkeypatch, tmp_path):
    payload = [
        {"username": "alice", "password": "pw", "email": " alice@example.com "},
        {"username": "bob", "password": "pw", "email": ""},
    ]
    path = tmp_path / "dev_users.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(core, "_DEV_USERS_PATH", path)

    users = core._load_devusers_json()

    assert users == [
        {
            "username": "alice",
            "password": "pw",
            "role": "user",
            "email": "alice@example.com",
            "is_active": True,
        },
        {
            "username": "bob",
            "password": "pw",
            "role": "user",
            "email": None,
            "is_active": True,
        },
    ]
