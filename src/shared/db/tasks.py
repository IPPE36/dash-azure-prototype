# src/shared/db/tasks.py

import os
from typing import Any, Iterable

from sqlalchemy import and_, select, delete, update, func

from .core import Payload, SessionLocal, Tasks


ACTIVE_TASK_STATUSES = {"PENDING", "RUNNING"}
_VERSION = os.getenv("APP_VERSION", "1.0")
_TASK_COLUMN_MAP = {
    "task_id": Tasks.task_id,
    "user_id": Tasks.user_id,
    "task_name": Tasks.task_name,
    "version": Tasks.version,
    "status": Tasks.status,
    "progress": Tasks.progress,
    "input_payload": Tasks.input_payload,
    "output_payload": Tasks.output_payload,
    "error_payload": Tasks.error_payload,
}
_DEFAULT_COLUMNS = (
    "task_id",
    "user_id",
    "task_name",
    "version",
    "status",
    "progress",
)


def add_task(user_id: int, task_name: str, input_payload: Payload) -> int | None:
    if SessionLocal is None:
        return None
    with SessionLocal() as session:
        row = Tasks(
            user_id=user_id,
            task_name=task_name,
            version=_VERSION,
            input_payload=input_payload,
            status="PENDING",
            progress=0,
        )
        session.add(row)
        session.commit()
        return row.task_id


def update_task(task_id: int, **kwargs: Any) -> bool:
    if SessionLocal is None or not kwargs:
        return False

    for key in kwargs:
        if key.endswith("_id"):
            raise ValueError(f"Task field is protected: {key}")
        if key not in _TASK_COLUMN_MAP:
            raise ValueError(f"Unknown task field: {key}")

    with SessionLocal() as session:
        stmt = (
            update(Tasks)
            .where(Tasks.task_id == task_id)
            .values(**kwargs)
        )
        result = session.execute(stmt)
        session.commit()
        return (result.rowcount or 0) > 0


def delete_task(task_id: int) -> bool:
    if SessionLocal is None:
        return False

    with SessionLocal() as session:
        stmt = delete(Tasks).where(Tasks.task_id == task_id)
        result = session.execute(stmt)
        session.commit()
        return (result.rowcount or 0) > 0


def get_task(task_id: int, *, include_payloads: bool = True) -> dict[str, Any] | None:
    if SessionLocal is None:
        return None

    selected = list(_DEFAULT_COLUMNS)
    if include_payloads:
        selected.extend(["input_payload", "output_payload", "error_payload"])

    cols = [_TASK_COLUMN_MAP[c].label(c) for c in selected]

    with SessionLocal() as session:
        stmt = select(*cols).where(Tasks.task_id == task_id).limit(1)
        row = session.execute(stmt).mappings().first()
        return dict(row) if row else None
    
    
def get_user_task_count(user_id: int, statuses: set[str] = ACTIVE_TASK_STATUSES) -> int:
    if SessionLocal is None:
        return 0
    with SessionLocal() as session:
        conditions = [Tasks.user_id == user_id]
        if statuses is not None:
            conditions.append(Tasks.status.in_(statuses))
        stmt = select(func.count()).select_from(Tasks).where(and_(*conditions))
        return session.scalar(stmt) or 0
    

def get_next_user_task_id(user_id: int) -> int | None:
    if SessionLocal is None:
        return None
    with SessionLocal() as session:
        stmt = (
            select(Tasks.task_id)
            .where(
                and_(
                    Tasks.user_id == user_id,
                    Tasks.status.in_(ACTIVE_TASK_STATUSES),
                )
            )
            .order_by(Tasks.task_id.asc())   # oldest first
            .limit(1)
        )
        return session.scalar(stmt)
    

def get_queue_length() -> int:
    if SessionLocal is None:
        return 0
    with SessionLocal() as session:
        stmt = select(func.count()).select_from(Tasks).where(
            Tasks.status.in_(ACTIVE_TASK_STATUSES)
        )
        return session.scalar(stmt) or 0
    
    
def get_queue_position(task_id: int) -> int | None:
    if SessionLocal is None:
        return None
    with SessionLocal() as session:
        stmt = (
            select(func.count())
            .select_from(Tasks)
            .where(
                Tasks.status.in_(ACTIVE_TASK_STATUSES),
                Tasks.task_id <= task_id,
            )
        )
        return session.scalar(stmt)
    

def get_user_task_rows(
    user_id: int,
    *,
    include_payloads: bool = True,
    newest_first: bool = True,
    limit: int | None = None,
    status: Iterable[str] | None = None,
    columns: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    if SessionLocal is None:
        return []

    if columns is None:
        selected = list(_DEFAULT_COLUMNS)
        if include_payloads:
            selected.extend(["input_payload", "output_payload", "error_payload"])
    else:
        selected = list(dict.fromkeys(columns))  # preserve order, remove duplicates

    invalid = set(selected) - set(_TASK_COLUMN_MAP)
    if invalid:
        raise ValueError(f"Invalid column(s): {sorted(invalid)}")

    selected_cols = [_TASK_COLUMN_MAP[c].label(c) for c in selected]

    with SessionLocal() as session:
        stmt = select(*selected_cols).where(Tasks.user_id == user_id)

        if status:
            status_values = list(status)
            stmt = stmt.where(Tasks.status.in_(status_values))

        stmt = stmt.order_by(Tasks.task_id.desc() if newest_first else Tasks.task_id.asc())

        if limit is not None:
            stmt = stmt.limit(limit)

        rows = session.execute(stmt).mappings().all()
        return [dict(row) for row in rows]