# src/shared/db/core.py

import logging
import subprocess
import zlib
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, create_engine, inspect, select, delete, text, func
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import DeclarativeBase, Mapped, sessionmaker, mapped_column
from sqlalchemy.schema import CreateColumn
from werkzeug.security import generate_password_hash

from shared.config import (
    DATABASE_URL,
    DB_BACKUP_DIR,
    DB_BACKUP_MAX_AGE_HOURS,
    DB_BACKUP_ON_STARTUP,
    DEV,
)


_CONFIGURED = False
_LOCK = threading.Lock()
_DEFAULT_DEV_USERS = (
    ("root", "123", "admin", "root@local.dev"),
    ("admin", "123", "admin", "admin@local.dev"),
    ("user", "123", "user", "user@local.dev"),
)

Payload = dict[str, Any] | list[Any] | str | int | float | bool | None

logger = logging.getLogger(__name__)

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_use_lifo=True,
    connect_args={
        "connect_timeout": 5,
        "application_name": "dash-azure-prototype",
        "options": (
            "-c statement_timeout=30000 "
            "-c lock_timeout=5000 "
            "-c idle_in_transaction_session_timeout=60000"
        ),
    },
) if DATABASE_URL else None

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
) if engine else None


class Base(DeclarativeBase):
    pass


class Users(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="user", server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Tasks(Base):
    __tablename__ = "tasks"
    task_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    task_name: Mapped[str] = mapped_column(String(128), nullable=True, default="New Task")
    tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[str] = mapped_column(String(32), default="v1")
    status: Mapped[str] = mapped_column(String(32))
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    input_payload: Mapped[Payload] = mapped_column(JSON)
    output_payload: Mapped[Payload] = mapped_column(JSON, nullable=True)
    error_payload: Mapped[Payload] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_backup_dir() -> Path:
    return Path(DB_BACKUP_DIR).expanduser().resolve()


def _latest_backup_at() -> datetime | None:
    backup_dir = _get_backup_dir()
    if not backup_dir.exists():
        return None
    dumps = sorted(backup_dir.glob("*.dump"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not dumps:
        return None
    return datetime.fromtimestamp(dumps[0].stat().st_mtime, tz=timezone.utc)


def _run_startup_backup() -> Path:
    backup_dir = _get_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = _utc_now().strftime("%d-%m-%Y")
    dump_path = backup_dir / f"dash_{ts}.dump"
    pg_dump_url = DATABASE_URL
    if "://" in pg_dump_url and "+" in pg_dump_url.split("://", 1)[0]:
        scheme, rest = pg_dump_url.split("://", 1)
        pg_dump_url = f"{scheme.split('+', 1)[0]}://{rest}"
    subprocess.run(
        [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--file",
            str(dump_path),
            pg_dump_url,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    logger.info("startup DB backup created", extra={"dump_path": str(dump_path)})
    return dump_path


def _assert_backup_fresh() -> bool:
    last = _latest_backup_at()
    if last is None:
        return False
    age = _utc_now() - last
    return age <= timedelta(hours=DB_BACKUP_MAX_AGE_HOURS)


def _sync_columns(conn) -> None:
    inspector = inspect(conn)
    preparer = conn.dialect.identifier_preparer

    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name, schema=table.schema):
            continue

        existing = {col["name"] for col in inspector.get_columns(table.name, schema=table.schema)}
        current = {col.name for col in table.columns}
        missing = [col for col in table.columns if col.name not in existing]
        extra = sorted(existing - current)
        for col in missing:
            col_def = str(CreateColumn(col).compile(dialect=conn.dialect))
            qualified_table = (
                f"{preparer.quote_schema(table.schema)}.{preparer.quote(table.name)}"
                if table.schema
                else preparer.quote(table.name)
            )
            conn.execute(text(f"ALTER TABLE {qualified_table} ADD COLUMN {col_def}"))
            logger.info("added missing DB column", extra={"table": table.name, "column": col.name})
        for col_name in extra:
            qualified_table = (
                f"{preparer.quote_schema(table.schema)}.{preparer.quote(table.name)}"
                if table.schema
                else preparer.quote(table.name)
            )
            quoted_col = preparer.quote(col_name)
            conn.execute(text(f"ALTER TABLE {qualified_table} DROP COLUMN IF EXISTS {quoted_col}"))
            logger.info("dropped extra DB column", extra={"table": table.name, "column": col_name})


def _add_dev_users() -> None:
    if SessionLocal is None:
        return
    with SessionLocal() as session:
        for username, password, role, email in _DEFAULT_DEV_USERS:
            existing = session.scalar(select(Users).where(Users.username == username))
            if existing is None:
                session.add(
                    Users(
                        username=username,
                        email=email,
                        password_hash=generate_password_hash(password),
                        role=role,
                        is_active=True,
                    )
                )
        session.commit()


def configure_db() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    with _LOCK:
        if _CONFIGURED:
            return
        _init_db()
        _CONFIGURED = True


def _init_db() -> None:
    if engine is None:
        logger.info("DATABASE_URL not set; skipping DB initialization")
        return
    lock_key = zlib.crc32(b"shared.db.init_db.create_all")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": lock_key})
            try:
                if not _assert_backup_fresh() and DB_BACKUP_ON_STARTUP:
                    try:
                        _run_startup_backup()
                    except FileNotFoundError:
                        logger.warning("pg_dump executable not found; continuing without startup backup")
                    except subprocess.CalledProcessError as exc:
                        logger.warning(
                            "startup DB backup failed; continuing app startup",
                            extra={"stderr": (exc.stderr or "").strip(), "stdout": (exc.stdout or "").strip()},
                        )
                Base.metadata.create_all(bind=conn)
                _sync_columns(conn)

                # remove stale tasks upon startup
                result = conn.execute(
                    delete(Tasks).where(Tasks.status.in_(["PENDING", "RUNNING"]))
                )
                logger.info("removed stale tasks", extra={"deleted": result.rowcount})

                conn.commit()
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})
    except DBAPIError:
        logger.exception("database schema initialization failed")
        raise
    if DEV:
        _add_dev_users()
    logger.info("database schema initialized")
