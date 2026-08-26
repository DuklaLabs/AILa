"""Opaque-token SSO shared by every AILa service.

RFID SSO: `authenticate_rfid(card_uid)` looks the card up in
`auth.rfid_cards` (joined to `auth.users`), checking `is_active` and the
`valid_from`/`valid_to` window.

Password login: `authenticate_password(username, password)` checks a
bcrypt hash in `auth.users.password_hash`.

Both issue an opaque token stored in `auth.web_sessions` (not JWT — chosen
so a session can be revoked immediately by deleting/expiring the DB row,
which is simpler to reason about for a small closed-network deployment
than distributing/rotating a JWT signing key across every service).
`get_current_user` is the FastAPI dependency every protected route in
every service should use instead of rolling its own cookie check.
"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Cookie, Depends, Header, HTTPException, status

from .db import get_pool
from .models import User

SESSION_COOKIE = "dl_session"
SESSION_TTL = timedelta(hours=int(os.getenv("SESSION_TTL_HOURS", "12")))

_USER_FIELDS = ("id", "username", "full_name", "email", "role", "is_active")
_USER_COLUMNS = ", ".join(_USER_FIELDS)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: Optional[str]) -> bool:
    if not password_hash:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


async def authenticate_password(username: str, password: str) -> Optional[User]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT {_USER_COLUMNS}, password_hash
            FROM auth.users
            WHERE username = $1 AND is_active
            """,
            username,
        )
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return User(**{field: row[field] for field in _USER_FIELDS})


async def authenticate_password_ignoring_active(username: str, password: str) -> Optional[User]:
    """Same check as authenticate_password but without the is_active
    filter — lets a caller tell "wrong password" apart from "correct
    password, account just isn't approved/active yet" so it can show an
    accurate message. Only reveals that distinction to someone who already
    proved they know the password, so it doesn't leak account existence
    to a blind guesser."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT {_USER_COLUMNS}, password_hash
            FROM auth.users
            WHERE username = $1
            """,
            username,
        )
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return User(**{field: row[field] for field in _USER_FIELDS})


async def authenticate_rfid(card_uid: str) -> Optional[User]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT u.id, u.username, u.full_name, u.email, u.role, u.is_active
            FROM auth.rfid_cards c
            JOIN auth.users u ON u.id = c.user_id
            WHERE c.card_uid = $1
              AND c.is_active
              AND u.is_active
              AND (c.valid_from IS NULL OR c.valid_from <= NOW())
              AND (c.valid_to IS NULL OR c.valid_to >= NOW())
            """,
            card_uid,
        )
    if row is None:
        return None
    return User(**dict(row))


async def create_session(user_id: int) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    # naive UTC — auth.web_sessions.expires_at is TIMESTAMP (no tz), matching
    # every other timestamp column in the schema (all populated via NOW()).
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + SESSION_TTL
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO auth.web_sessions (token, user_id, expires_at)
            VALUES ($1, $2, $3)
            """,
            token,
            user_id,
            expires_at,
        )
    return token, expires_at


async def revoke_session(token: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE auth.web_sessions SET revoked_at = NOW() WHERE token = $1",
            token,
        )


async def get_user_from_token(token: Optional[str]) -> Optional[User]:
    if not token:
        return None
    qualified_columns = ", ".join(f"u.{field}" for field in _USER_FIELDS)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT {qualified_columns}
            FROM auth.web_sessions s
            JOIN auth.users u ON u.id = s.user_id
            WHERE s.token = $1
              AND s.revoked_at IS NULL
              AND s.expires_at > NOW()
              AND u.is_active
            """,
            token,
        )
    if row is None:
        return None
    return User(**dict(row))


async def get_current_user(
    dl_session: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None),
) -> User:
    token = dl_session
    if token is None and authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ")

    user = await get_user_from_token(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_role(*roles: str):
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return _check
