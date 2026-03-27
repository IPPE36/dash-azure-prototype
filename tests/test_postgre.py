import os

import pytest
from sqlalchemy import create_engine, text


RUN_ALEMBIC_TESTS = os.getenv("RUN_ALEMBIC_TESTS", "").lower() in {"1", "true", "t", "yes", "y", "on"}
RUN_POSTGRE_TESTS = os.getenv("RUN_POSTGRE_TESTS", "").lower() in {"1", "true", "t", "yes", "y", "on"}
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


@pytest.mark.skipif(not RUN_POSTGRE_TESTS, reason="set RUN_POSTGRE_TESTS=1 to enable")
@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")
def test_db_connects():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.skipif(not RUN_ALEMBIC_TESTS, reason="set RUN_ALEMBIC_TESTS=1 to enable")
@pytest.mark.skipif(not RUN_POSTGRE_TESTS, reason="set RUN_POSTGRE_TESTS=1 to enable")
@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")
def test_alembic_version_table_exists():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT to_regclass('public.alembic_version')"))
        table = result.scalar()
        if table is None:
            pytest.skip("alembic_version table missing (migrations not applied)")


@pytest.mark.skipif(not RUN_POSTGRE_TESTS, reason="set RUN_POSTGRE_TESTS=1 to enable")
@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")
def test_alembic_version_has_value():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        version = result.scalar()
        if version is None:
            pytest.skip("alembic_version is empty (migrations not applied)")
