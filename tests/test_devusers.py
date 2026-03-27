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