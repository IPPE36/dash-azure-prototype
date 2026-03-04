# src/shared/db/users.py

from sqlalchemy import select
from werkzeug.security import check_password_hash

from .core import SessionLocal, Users


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
        session.add(
            Users(
                username=normalized,
                password_hash=password_hash or "",
                role=normalized_role,
                is_active=True,
            )
        )
        session.commit()
