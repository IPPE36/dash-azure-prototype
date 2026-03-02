import logging
import os

from sqlalchemy import DateTime, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .logs import log_execution

logger = logging.getLogger(__name__)

_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

engine = create_engine(_DATABASE_URL, future=True, pool_pre_ping=True) if _DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False) if engine else None


class Base(DeclarativeBase):
    pass


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


@log_execution(logger_name=__name__)
def init_db() -> None:
    if engine is None:
        logger.info("DATABASE_URL not set; skipping DB initialization")
        return
    Base.metadata.create_all(bind=engine)
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
