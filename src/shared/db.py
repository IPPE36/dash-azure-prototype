# src/shared/db.py

import logging
import os

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

from .logs import log_execution


_DEV = os.getenv("DEV", "true").lower() == "true"
_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
_DEFAULT_DEV_USERS = (
    ("root", "123"),
    ("admin", "123"),
    ("user", "123"),
)

logger = logging.getLogger(__name__)

engine = create_engine(_DATABASE_URL, future=True, pool_pre_ping=True) if _DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False) if engine else None


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TaskRun(Base):
    __tablename__ = "task_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    task_name: Mapped[str] = mapped_column(String(128))
    input_value: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    result_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def _seed_dev_users() -> None:
    if SessionLocal is None:
        return
    with SessionLocal() as session:
        for username, password in _DEFAULT_DEV_USERS:
            existing = session.scalar(select(User).where(User.username == username))
            if existing is None:
                session.add(
                    User(
                        username=username,
                        password_hash=generate_password_hash(password),
                        is_active=True,
                    )
                )
        session.commit()


@log_execution(logger_name=__name__)
def auth_dev_user(username: str, password: str) -> bool:
    if SessionLocal is None:
        return False
    normalized = username.strip()
    if not normalized or not password:
        return False
    with SessionLocal() as session:
        row = session.scalar(select(User).where(User.username == normalized))
        if row is None or not row.is_active:
            return False
        return check_password_hash(row.password_hash, password)
    

@log_execution(logger_name=__name__)
def add_user(username: str, password_hash: str = "", exists_ok: bool = True) -> None:
    if SessionLocal is None:
        return
    normalized = username.strip()
    if not normalized:
        return
    with SessionLocal() as session:
        row = session.scalar(select(User).where(User.username == normalized))
        if row is not None:
            if exists_ok:
                return
            raise ValueError(f"User already exists: {normalized}")
        session.add(
            User(
                username=normalized,
                password_hash=password_hash or "",
                is_active=True,
            )
        )
        session.commit()


@log_execution(logger_name=__name__)
def init_db() -> None:
    if engine is None:
        logger.info("DATABASE_URL not set; skipping DB initialization")
        return
    Base.metadata.create_all(bind=engine)
    if _DEV:
        _seed_dev_users()
    logger.info("database schema initialized")


@log_execution(logger_name=__name__)
def create_task_run(task_id: str, task_name: str, input_value: int) -> None:
    if SessionLocal is None:
        return
    with SessionLocal() as session:
        row = TaskRun(
            task_id=task_id,
            task_name=task_name,
            input_value=input_value,
            status="STARTED",
        )
        session.add(row)
        session.commit()


@log_execution(logger_name=__name__)
def update_task_run(
    task_id: str, status: str, result_text: str | None = None, error_text: str | None = None
) -> None:
    if SessionLocal is None:
        return
    with SessionLocal() as session:
        row = session.scalar(select(TaskRun).where(TaskRun.task_id == task_id))
        if row is None:
            return
        row.status = status
        row.result_text = result_text
        row.error_text = error_text
        session.commit()


@log_execution(logger_name=__name__)
def get_task_run(task_id: str) -> dict[str, str | int | None] | None:
    if SessionLocal is None:
        return None
    with SessionLocal() as session:
        row = session.scalar(select(TaskRun).where(TaskRun.task_id == task_id))
        if row is None:
            return None
        return {
            "task_id": row.task_id,
            "task_name": row.task_name,
            "input_value": row.input_value,
            "status": row.status,
            "result_text": row.result_text,
            "error_text": row.error_text,
        }


