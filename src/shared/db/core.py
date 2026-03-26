import json
import logging
import threading
import zlib
from pathlib import Path
from typing import Any, TypedDict

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    JSON,
    String,
    ForeignKey,
    create_engine,
    select,
    delete,
    text,
    update,
    func,
)
from sqlalchemy.exc import DBAPIError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, sessionmaker, mapped_column
from werkzeug.security import check_password_hash, generate_password_hash

from shared.config import DATABASE_URL, DESKTOP, AUTH_MODE

_CONFIGURED = False
_LOCK = threading.Lock()
_DEV_USERS_PATH = Path(__file__).resolve().parents[3] / "dev_users.json"

Payload = dict[str, Any] | list[Any] | str | int | float | bool | None

class DevUser(TypedDict):
    username: str
    password: str
    role: str
    email: str | None
    is_active: bool

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
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="user", server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Tasks(Base):
    __tablename__ = "tasks"
    task_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), index=True, nullable=False)
    task_name: Mapped[str] = mapped_column(String(128), nullable=True, default="New Task")
    tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[str] = mapped_column(String(32), default="v1")
    status: Mapped[str] = mapped_column(String(32))
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    input_payload: Mapped[Payload] = mapped_column(JSON)
    output_payload: Mapped[Payload] = mapped_column(JSON, nullable=True)
    error_payload: Mapped[Payload] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


def _clear_stale_tasks(session) -> None:
    result = session.execute(delete(Tasks).where(Tasks.status.in_(["PENDING", "RUNNING"])))
    logger.info("removed stale tasks", extra={"deleted": result.rowcount})


def _sync_devusers(session) -> None:
    users = _load_devusers_json()
    desired_usernames = {user["username"] for user in users}

    uploaded = 0
    updated = 0
    deactivated = 0

    for user in users:
        existing = session.scalar(select(Users).where(Users.username == user["username"]))
        if existing is None:
            session.add(
                Users(
                    username=user["username"],
                    email=user.get("email"),
                    password_hash=generate_password_hash(user["password"]),
                    role=user["role"],
                    is_active=user["is_active"],
                )
            )
            uploaded += 1
            continue

        changed = False

        if not check_password_hash(existing.password_hash, user["password"]):
            existing.password_hash = generate_password_hash(user["password"])
            changed = True

        if existing.role != user["role"]:
            existing.role = user["role"]
            changed = True

        if existing.email != user.get("email"):
            existing.email = user.get("email")
            changed = True

        if existing.is_active != user["is_active"]:
            existing.is_active = user["is_active"]
            changed = True

        if changed:
            updated += 1

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
        extra={"added": uploaded, "updated": updated, "deactivated": deactivated},
    )


def _load_devusers_json() -> list[DevUser]:
    if not _DEV_USERS_PATH.exists():
        return []

    try:
        payload = json.loads(_DEV_USERS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(
            "failed to read dev users json; skipping dev seeding",
            extra={"path": str(_DEV_USERS_PATH), "error": str(e)},
        )
        return []

    if not isinstance(payload, list):
        logger.warning(
            "dev users json must be a list; skipping dev seeding",
            extra={"path": str(_DEV_USERS_PATH), "type": type(payload).__name__},
        )
        return []

    users: list[DevUser] = []

    for entry in payload:
        if not isinstance(entry, dict):
            continue

        username = str(entry.get("username", "")).strip()
        password = str(entry.get("password", "")).strip()

        if not username or not password:
            continue

        users.append(
            {
                "username": username,
                "password": password,
                "role": str(entry.get("role", "user")).strip() or "user",
                "email": str(entry.get("email")).strip() if entry.get("email") else None,
                "is_active": bool(entry.get("is_active", True)),
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
        logger.info("DATABASE_URL not set; skipping initialization")
        return

    try:
        with engine.begin() as conn:
            lock_key = zlib.crc32(b"shared.db.init_db")
            conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})

            with SessionLocal(bind=conn) as session:
                _clear_stale_tasks(session)
                if DESKTOP and AUTH_MODE == "dev":
                    _sync_devusers(session)
                elif DESKTOP and AUTH_MODE == "msal":
                    pass
                session.flush()

    except DBAPIError:
        logger.exception("database schema initialization failed")
        raise

    logger.info("database schema initialized")