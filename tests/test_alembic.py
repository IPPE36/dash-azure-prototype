import os
from pathlib import Path

import pytest
from alembic.config import Config


RUN_ALEMBIC_TESTS = os.getenv("RUN_ALEMBIC_TESTS", "").lower() in {"1", "true", "t", "yes", "y", "on"}


@pytest.mark.skipif(not RUN_ALEMBIC_TESTS, reason="set RUN_ALEMBIC_TESTS=1 to enable")
def test_alembic_config_loads():
    root = Path(__file__).resolve().parents[1]
    ini_path = root / "alembic.ini"
    cfg = Config(str(ini_path))
    script_location = cfg.get_main_option("script_location")
    assert script_location is not None
    assert "alembic" in script_location


@pytest.mark.skipif(not RUN_ALEMBIC_TESTS, reason="set RUN_ALEMBIC_TESTS=1 to enable")
def test_alembic_script_location_exists():
    root = Path(__file__).resolve().parents[1]
    ini_path = root / "alembic.ini"
    cfg = Config(str(ini_path))
    script_location = cfg.get_main_option("script_location")
    assert script_location is not None
    location_path = (root / "alembic") if "alembic" in script_location else root / script_location
    assert location_path.exists()
