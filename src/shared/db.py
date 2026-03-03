# src/shared/db.py

import logging
import os
import zlib
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, create_engine, desc, inspect, select, text, func
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import DeclarativeBase, Mapped, sessionmaker, mapped_column
from sqlalchemy.schema import CreateColumn
from werkzeug.security import check_password_hash, generate_password_hash

from .logs import log_execution


Payload = dict[str, Any] | list[Any] | str | int | float | bool | None

_DEV = os.getenv("DEV", "true").lower() == "true"
_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
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
    task_name: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[str] = mapped_column(String(32), default="v1")
    status: Mapped[str] = mapped_column(String(32), index=True)
    input_payload: Mapped[Payload] = mapped_column(JSON)
    output_payload: Mapped[Payload] = mapped_column(JSON, nullable=True)
    error_payload: Mapped[Payload] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


def _sync_missing_columns(conn) -> None:
    inspector = inspect(conn)
    preparer = conn.dialect.identifier_preparer

    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name, schema=table.schema):
            continue

        existing = {col["name"] for col in inspector.get_columns(table.name, schema=table.schema)}
        missing = [col for col in table.columns if col.name not in existing]
        for col in missing:
            col_def = str(CreateColumn(col).compile(dialect=conn.dialect))
            qualified_table = (
                f"{preparer.quote_schema(table.schema)}.{preparer.quote(table.name)}"
                if table.schema
                else preparer.quote(table.name)
            )
            conn.execute(text(f"ALTER TABLE {qualified_table} ADD COLUMN {col_def}"))
            logger.info("added missing DB column", extra={"table": table.name, "column": col.name})


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
                Base.metadata.create_all(bind=conn)
                _sync_missing_columns(conn)
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
    task_name: str,
    input_payload: Payload,
    version: str = "v1",
) -> int | None:
    if SessionLocal is None:
        return None
    with SessionLocal() as session:
        row = Tasks(
            task_name=task_name,
            version=version,
            input_payload=input_payload,
            status="STARTED",
        )
        session.add(row)
        session.commit()
        return row.task_id


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
    with SessionLocal() as session:
        if task_id is not None:
            row = session.scalar(select(Tasks).where(Tasks.task_id == task_id))
        elif task_name:
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
        row.status = status
        row.output_payload = output_payload
        row.error_payload = error_payload
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
                    .where(Tasks.task_name == raw)
                    .order_by(desc(Tasks.created_at))
                    .limit(1)
                )
        if row is None:
            return None
        return {
            "task_id": row.task_id,
            "task_name": row.task_name,
            "version": row.version,
            "status": row.status,
            "input_payload": row.input_payload,
            "output_payload": row.output_payload,
            "error_payload": row.error_payload,
        }
