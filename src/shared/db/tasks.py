# src/shared/db/tasks.py

from typing import Any

from sqlalchemy import and_, desc, func, or_, select

from .core import ACTIVE_TASK_STATUSES, Payload, SessionLocal, Tasks, _utc_now


def add_task(
    celery_task_id: str,
    task_name: str,
    input_payload: Payload,
    version: str = "v1",
    user_id: str | None = None,
    status: str = "STARTED",
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
            status=status,
        )
        session.add(row)
        session.commit()
        return row.task_id


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


def get_task_queue_position(task_ref: int | str) -> dict[str, Any] | None:
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

        if row is None:
            return None

        total_active = session.scalar(
            select(func.count()).select_from(Tasks).where(Tasks.status.in_(ACTIVE_TASK_STATUSES))
        ) or 0

        if row.status not in ACTIVE_TASK_STATUSES:
            return {
                "status": row.status,
                "position": None,
                "total_active": int(total_active),
                "user_position": None,
                "user_total_active": 0,
            }

        ahead = session.scalar(
            select(func.count())
            .select_from(Tasks)
            .where(
                Tasks.status.in_(ACTIVE_TASK_STATUSES),
                or_(
                    Tasks.created_at < row.created_at,
                    and_(Tasks.created_at == row.created_at, Tasks.task_id < row.task_id),
                ),
            )
        ) or 0

        user_total_active = 0
        user_position = None
        if row.user_id:
            user_total_active = session.scalar(
                select(func.count())
                .select_from(Tasks)
                .where(
                    Tasks.status.in_(ACTIVE_TASK_STATUSES),
                    Tasks.user_id == row.user_id,
                )
            ) or 0
            user_ahead = session.scalar(
                select(func.count())
                .select_from(Tasks)
                .where(
                    Tasks.status.in_(ACTIVE_TASK_STATUSES),
                    Tasks.user_id == row.user_id,
                    or_(
                        Tasks.created_at < row.created_at,
                        and_(Tasks.created_at == row.created_at, Tasks.task_id < row.task_id),
                    ),
                )
            ) or 0
            user_position = int(user_ahead) + 1

        return {
            "status": row.status,
            "position": int(ahead) + 1,
            "total_active": int(total_active),
            "user_position": user_position,
            "user_total_active": int(user_total_active),
        }


def get_user_task_monitor(user_id: str | None) -> dict[str, Any]:
    normalized_user = (user_id or "").strip()
    if SessionLocal is None or not normalized_user:
        return {"mode": "idle"}

    running_statuses = ("RECEIVED", "STARTED", "RETRY")
    with SessionLocal() as session:
        active_row = session.scalar(
            select(Tasks)
            .where(
                Tasks.user_id == normalized_user,
                Tasks.status.in_(ACTIVE_TASK_STATUSES),
            )
            .order_by(Tasks.created_at.asc(), Tasks.task_id.asc())
            .limit(1)
        )
        if active_row is not None:
            mode = "running" if active_row.status in running_statuses else "pending"
            duration_s = 10
            if isinstance(active_row.input_payload, dict):
                duration_s = max(1, int(active_row.input_payload.get("duration_s", 10)))
            started_at = active_row.updated_at or active_row.created_at
            elapsed = 0.0
            if started_at is not None:
                elapsed = max(0.0, (_utc_now() - started_at).total_seconds())
            progress = min(95, int((elapsed / duration_s) * 100)) if mode == "running" else 0

            ahead = session.scalar(
                select(func.count())
                .select_from(Tasks)
                .where(
                    Tasks.status.in_(ACTIVE_TASK_STATUSES),
                    or_(
                        Tasks.created_at < active_row.created_at,
                        and_(
                            Tasks.created_at == active_row.created_at,
                            Tasks.task_id < active_row.task_id,
                        ),
                    ),
                )
            ) or 0
            total_active = session.scalar(
                select(func.count()).select_from(Tasks).where(Tasks.status.in_(ACTIVE_TASK_STATUSES))
            ) or 0

            return {
                "mode": mode,
                "db_task_id": active_row.task_id,
                "task_id": active_row.celery_task_id,
                "state": active_row.status,
                "progress": progress,
                "position": int(ahead) + 1,
                "total_active": int(total_active),
            }

    return {"mode": "idle"}


def delete_task_run(task_ref: int | str) -> bool:
    if SessionLocal is None:
        return False
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
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True
