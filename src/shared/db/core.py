# src/shared/db/core.py
# Design note: DB bootstrap happens once per process and is protected by a
# Postgres advisory lock to avoid concurrent schema edits across workers.
# We keep a small pool to suit low-concurrency workloads and limit connections.
# Default dev users are seeded only when DEV=true for quick local access.
# To configure dev users, create dev_users.json at the repo root (ignored by git)
# e.g. {"username": "admin", "password": "123", "role": "admin", "email": "admin@local.dev"}

import json
import logging
import zlib
import threading
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, create_engine, inspect, select, delete, text, func, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import DeclarativeBase, Mapped, sessionmaker, mapped_column
from sqlalchemy.schema import CreateColumn
from werkzeug.security import check_password_hash, generate_password_hash

from shared.config import (
    DATABASE_URL,
    DESKTOP,
    AUTH_MODE,
)
_CONFIGURED = False
_LOCK = threading.Lock()
_DEV_USERS_PATH = Path(__file__).resolve().parents[3] / "dev_users.json"

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
        if extra:
            logger.info("extra DB columns detected (not dropped)", extra={"table": table.name, "columns": extra})

def _clear_stale_tasks(session) -> None:
    result = session.execute(delete(Tasks).where(Tasks.status.in_(["PENDING", "RUNNING"])))
    logger.info("removed stale tasks", extra={"deleted": result.rowcount})


def _sync_devusers(session) -> None:
    existing_count = session.scalar(select(func.count()).select_from(Users)) or 0
    if existing_count == 0:
        logger.info(
            "no users found; create dev users via %s (see format in src/shared/db/core.py)",
            str(_DEV_USERS_PATH),
        )
    users = _load_devusers_json()
    if not users:
        logger.info("no dev users configured; skipping dev seeding", extra={"path": str(_DEV_USERS_PATH)})
        return
    desired_usernames = {user["username"] for user in users}
    upserted = 0
    updated = 0
    for user in users:
        username = user["username"] or ""
        password = user["password"] or ""
        role = user["role"] or "user"
        email = user["email"]
        is_active = bool(user.get("is_active", True))
        existing = session.scalar(select(Users).where(Users.username == username))
        if existing is None:
            session.add(
                Users(
                    username=username,
                    email=email,
                    password_hash=generate_password_hash(password),
                    role=role,
                    is_active=is_active,
                )
            )
            upserted += 1
            continue
        changed = False
        if not check_password_hash(existing.password_hash, password):
            existing.password_hash = generate_password_hash(password)
            changed = True
        if existing.role != role:
            existing.role = role
            changed = True
        if existing.email != email:
            existing.email = email
            changed = True
        if existing.is_active != is_active:
            existing.is_active = is_active
            changed = True
        if changed:
            updated += 1
    deactivated = 0
    if desired_usernames:
        inactive_rows = session.scalars(
            select(Users).where(
                Users.username.notin_(desired_usernames),
                Users.is_active.is_(True),
            )
        )
        for row in inactive_rows:
            row.is_active = False
            deactivated += 1
    logger.info(
        "dev users synced",
        extra={"added": upserted, "updated": updated, "deactivated": deactivated},
    )

def _deactivate_devusers(session) -> None:
    users = _load_devusers_json()
    if not users:
        logger.info("no dev users configured; skipping dev deactivation", extra={"path": str(_DEV_USERS_PATH)})
        return
    usernames = {user["username"] for user in users}
    deactivated = session.execute(
        update(Users)
        .where(Users.username.in_(usernames), Users.is_active.is_(True))
        .values(is_active=False)
    ).rowcount or 0
    logger.info(
        "dev users deactivated for msal mode",
        extra={"deactivated": deactivated},
    )


def _load_devusers_json() -> list[dict[str, str | None]]:
    if not _DEV_USERS_PATH.exists():
        return []
    try:
        payload = json.loads(_DEV_USERS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "failed to read dev users json; skipping dev seeding",
            extra={"path": str(_DEV_USERS_PATH), "error": str(exc)},
        )
        return []
    if not isinstance(payload, list):
        logger.warning(
            "dev users json must be a list; skipping dev seeding",
            extra={"path": str(_DEV_USERS_PATH), "type": type(payload).__name__},
        )
        return []
    users: list[dict[str, str | None | bool]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        username = str(entry.get("username", "")).strip()
        password = str(entry.get("password", "")).strip()
        if not username or not password:
            continue
        role = str(entry.get("role", "user")).strip() or "user"
        email_value = entry.get("email")
        email = str(email_value).strip() if email_value else None
        is_active = bool(entry.get("is_active", True))
        users.append(
            {
                "username": username,
                "password": password,
                "role": role,
                "email": email,
                "is_active": is_active,
            }
        )
    return users


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
                Base.metadata.create_all(bind=conn)
                _sync_columns(conn)
                with SessionLocal(bind=conn) as session:
                    _clear_stale_tasks(session)
                    if DESKTOP and AUTH_MODE == "dev":
                        _sync_devusers(session)
                    elif DESKTOP and AUTH_MODE == "msal":
                        _deactivate_devusers(session)
                    session.commit()
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})
    except DBAPIError:
        logger.exception("database schema initialization failed")
        raise
    logger.info("database schema initialized")
