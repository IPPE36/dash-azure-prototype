# src/shared/db.py

import logging
import os
import subprocess
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, create_engine, desc, inspect, select, text, func
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import DeclarativeBase, Mapped, sessionmaker, mapped_column
from sqlalchemy.schema import CreateColumn
from werkzeug.security import check_password_hash, generate_password_hash

from .logs import log_execution


# dtype for payloads:
Payload = dict[str, Any] | list[Any] | str | int | float | bool | None

_DEV = os.getenv("DEV", "true").lower() == "true"
_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
_BACKUP_ON_STARTUP = os.getenv("DB_BACKUP_ON_STARTUP", "true").lower() == "true"
_BACKUP_DIR = os.getenv("DB_BACKUP_DIR", "./db_backups").strip() or "./db_backups"
_BACKUP_MAX_AGE_HOURS = int(os.getenv("DB_BACKUP_MAX_AGE_HOURS", "168"))
_DEFAULT_DEV_USERS = (
    ("root", "123", "admin"),
    ("admin", "123", "admin"),
    ("user", "123", "user"),
)

logger = logging.getLogger(__name__)

engine = create_engine(
    _DATABASE_URL,
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
    )},
) if _DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False) if engine else None


class Base(DeclarativeBase):
    pass


class Users(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="user", server_default="user", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Tasks(Base):
    __tablename__ = "tasks"
    task_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    task_name: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    version: Mapped[str] = mapped_column(String(32), default="v1")
    status: Mapped[str] = mapped_column(String(32), index=True)
    input_payload: Mapped[Payload] = mapped_column(JSON)
    output_payload: Mapped[Payload] = mapped_column(JSON, nullable=True)
    error_payload: Mapped[Payload] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())



def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_backup_dir() -> Path:
    return Path(_BACKUP_DIR).expanduser().resolve()


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
    pg_dump_url = _DATABASE_URL
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
    return age <= timedelta(hours=_BACKUP_MAX_AGE_HOURS)
    

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
        for username, password, role in _DEFAULT_DEV_USERS:
            existing = session.scalar(select(Users).where(Users.username == username))
            if existing is None:
                session.add(Users(
                    username=username,
                    password_hash=generate_password_hash(password),
                    role=role,
                    is_active=True,
                ))
        session.commit()


@log_execution(logger_name=__name__)
def auth_dev_user(username: str, password: str) -> bool:
    if SessionLocal is None:
        return False
    normalized = username.strip()
    if not normalized or not password:
        return False
    with SessionLocal() as session:
        row = session.scalar(select(Users).where(Users.username == normalized))
        if row is None or not row.is_active:
            return False
        return check_password_hash(row.password_hash, password)


@log_execution(logger_name=__name__)
def add_user(username: str, password_hash: str = "", role: str = "user", exists_ok: bool = True) -> None:
    if SessionLocal is None:
        return
    normalized = username.strip()
    if not normalized:
        return
    normalized_role = role.strip().lower() if role and role.strip() else "user"
    with SessionLocal() as session:
        row = session.scalar(select(Users).where(Users.username == normalized))
        if row is not None:
            if exists_ok:
                return
            raise ValueError(f"User already exists: {normalized}")
        session.add(Users(
            username=normalized,
            password_hash=password_hash or "",
            role=normalized_role,
            is_active=True,
        ))
        session.commit()


@log_execution(logger_name=__name__)
def init_db() -> None:
    if engine is None:
        logger.info("DATABASE_URL not set; skipping DB initialization")
        return
    # Multiple processes can import app startup code concurrently; serialize DDL in Postgres.
    lock_key = zlib.crc32(b"shared.db.init_db.create_all")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": lock_key})
            try:
                if not _assert_backup_fresh() and _BACKUP_ON_STARTUP:
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
                conn.commit()
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})
    except DBAPIError:
        logger.exception("database schema initialization failed")
        raise
    if _DEV:
        _add_dev_users()
    logger.info("database schema initialized")


@log_execution(logger_name=__name__)
def add_task(
    celery_task_id: str,
    task_name: str,
    input_payload: Payload,
    version: str = "v1",
    user_id: str | None = None,
) -> int | None:
    if SessionLocal is None:
        return None
    with SessionLocal() as session:
        row = Tasks(
            celery_task_id=celery_task_id,
            task_name=task_name,
            user_id=user_id.strip() if isinstance(user_id, str) and user_id.strip() else None,
            version=version,
            input_payload=input_payload,
            status="STARTED",
        )
        session.add(row)
        session.commit()
        return row.task_id


@log_execution(logger_name=__name__)
def update_task(task_id: int, **kwargs: Any) -> bool:
    if SessionLocal is None or not kwargs:
        return False
    with SessionLocal() as session:
        row = session.scalar(select(Tasks).where(Tasks.task_id == task_id))
        if row is None:
            return False
        for field, value in kwargs.items():
            if field == "task_id":
                continue
            if not hasattr(row, field):
                raise ValueError(f"Unknown task field: {field}")
            setattr(row, field, value)
        session.commit()
        return True


@log_execution(logger_name=__name__)
def update_task_run(
    status: str,
    task_id: int | None = None,
    task_name: str | None = None,
    output_payload: Payload = None,
    error_payload: Payload = None,
) -> None:
    if SessionLocal is None:
        return
    payload = {
        "status": status,
        "output_payload": output_payload,
        "error_payload": error_payload,
    }
    if task_id is not None:
        update_task(task_id=task_id, **payload)
        return

    with SessionLocal() as session:
        if task_name:
            row = session.scalar(
                select(Tasks)
                .where(Tasks.task_name == task_name)
                .order_by(desc(Tasks.created_at))
                .limit(1)
            )
        else:
            return
        if row is None:
            return
        for field, value in payload.items():
            setattr(row, field, value)
        session.commit()


@log_execution(logger_name=__name__)
def get_task_run(task_ref: int | str) -> dict[str, Any] | None:
    if SessionLocal is None:
        return None
    with SessionLocal() as session:
        row = None
        if isinstance(task_ref, int):
            row = session.scalar(select(Tasks).where(Tasks.task_id == task_ref))
        else:
            raw = str(task_ref).strip()
            if raw.isdigit():
                row = session.scalar(select(Tasks).where(Tasks.task_id == int(raw)))
            if row is None and raw:
                row = session.scalar(
                    select(Tasks)
                    .where(Tasks.celery_task_id == raw)
                    .order_by(desc(Tasks.created_at))
                    .limit(1)
                )
            if row is None and raw:
                row = session.scalar(
                    select(Tasks)
                    .where(Tasks.task_name == raw)
                    .order_by(desc(Tasks.created_at))
                    .limit(1)
                )
        if row is None:
            return None
        return {
            "task_id": row.task_id,
            "celery_task_id": row.celery_task_id,
            "task_name": row.task_name,
            "user_id": row.user_id,
            "version": row.version,
            "status": row.status,
            "input_payload": row.input_payload,
            "output_payload": row.output_payload,
            "error_payload": row.error_payload,
        }
