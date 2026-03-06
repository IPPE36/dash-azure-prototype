# src/shared/db/tasks.py

import os
from typing import Any

from sqlalchemy import and_, select, update, func

from .core import Payload, SessionLocal, Tasks


ACTIVE_TASK_STATUSES = {"PENDING", "RUNNING"}
_VERSION = os.getenv("APP_VERSION", "1.0")


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
    with SessionLocal() as session:
        row = session.scalar(select(Tasks).where(Tasks.task_id == task_id).limit(1))
        if row is None:
            return False
        for key, value in kwargs.items():
            if key.endswith("_id"):
                raise ValueError(f"Task field is protected: {key}")
            if not hasattr(row, key):
                raise ValueError(f"Unknown task field: {key}")
            setattr(row, key, value)
        session.commit()
        return True
    

def delete_task(task_id: int) -> bool:
    if SessionLocal is None:
        return False
    with SessionLocal() as session:
        row = session.scalar(select(Tasks).where(Tasks.task_id == task_id).limit(1))
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True


def get_task(task_id: int) -> dict[str, Any] | None:
    if SessionLocal is None:
        return None
    with SessionLocal() as session:
        row = session.scalar(select(Tasks).where(Tasks.task_id == task_id))
        if row is None:
            return None
        return {
            "task_id": row.task_id,
            "user_id": row.user_id,
            "celery_id": row.celery_id,
            "task_name": row.task_name,
            "version": row.version,
            "status": row.status,
            "progress": row.progress,
            "input_payload": row.input_payload,
            "output_payload": row.output_payload,
            "error_payload": row.error_payload,
        }
    
def get_user_active_task_count(user_id: int) -> int:
    if SessionLocal is None:
        return 0
    with SessionLocal() as session:
        stmt = select(func.count()).select_from(Tasks).where(
            and_(
                Tasks.user_id == user_id,
                Tasks.status.in_(ACTIVE_TASK_STATUSES),
            )
        )
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
        row = session.scalar(select(Tasks.task_id).where(Tasks.task_id == task_id).limit(1))
        if row is None:
            return None
        stmt = select(func.count()).select_from(Tasks).where(
            and_(
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
) -> list[dict[str, Any]]:
    """
    Returns user tasks as list[dict], suitable for pd.DataFrame(rows).
    - include_payloads: include input/output/error payload dicts (can be large)
    - newest_first: order by task_id desc (default) else asc
    - limit: optionally cap number of rows
    """
    if SessionLocal is None:
        return []
    with SessionLocal() as session:
        stmt = select(Tasks).where(Tasks.user_id == user_id)
        if newest_first:
            stmt = stmt.order_by(Tasks.task_id.desc())
        else:
            stmt = stmt.order_by(Tasks.task_id.asc())
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = session.scalars(stmt).all()

        out: list[dict[str, Any]] = []
        for row in rows:
            item: dict[str, Any] = {
                "task_id": row.task_id,
                "user_id": row.user_id,
                "celery_id": row.celery_id,
                "task_name": row.task_name,
                "version": row.version,
                "status": row.status,
                "progress": row.progress,
            }
            if include_payloads:
                item.update(
                    {
                        "input_payload": row.input_payload,
                        "output_payload": row.output_payload,
                        "error_payload": row.error_payload,
                    }
                )
            out.append(item)
        return out
    

def set_celery_id(task_id: int, celery_id: str) -> None:
    if SessionLocal is None:
        return

    with SessionLocal() as session:
        session.execute(
            update(Tasks)
            .where(Tasks.task_id == task_id)
            .values(celery_id=celery_id)
        )
        session.commit()