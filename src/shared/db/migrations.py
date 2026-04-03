# src/shared/db/migrations.py
# Design notes (DB changes):
# - Update SQLAlchemy models in `src/shared/db/core.py` first.
# - Generate a new Alembic revision (`alembic revision --autogenerate -m "..."`).
# - Review the new file under `alembic/versions/` and adjust if needed.
# - Apply it with `alembic upgrade head` (entrypoint runs this when RUN_MIGRATIONS=true).
# - Data seeding (dev users, cleanup) is handled separately in `shared.db.bootstrap`.

import logging
import os
import zlib
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from shared.db.core import engine


logger = logging.getLogger(__name__)


def run_migrations() -> None:
    if engine is None:
        logger.info("DATABASE_URL not set; skipping alembic migrations")
        return

    lock_key = zlib.crc32(b"shared.db.migrations.alembic")
    alembic_ini_path = Path(__file__).resolve().parents[3] / "alembic.ini"

    try:
        with engine.begin() as conn:
            acquired = conn.scalar(
                text("SELECT pg_try_advisory_xact_lock(:k)"),
                {"k": lock_key},
            )

            if not acquired:
                logger.info("another replica is running migrations; skipping")
                return

            cfg = Config(str(alembic_ini_path))

            db_url = os.getenv("DATABASE_URL")
            if db_url:
                cfg.set_main_option("sqlalchemy.url", db_url)

            # Critical: force Alembic to use the same DB connection that holds the lock.
            cfg.attributes["connection"] = conn

            command.upgrade(cfg, "head")
            logger.info("alembic migrations completed")

    except Exception:
        logger.exception("alembic migrations failed")
        raise


def main() -> None:
    from shared.log import configure_logs
    configure_logs()
    run_migrations()


if __name__ == "__main__":
    main()
