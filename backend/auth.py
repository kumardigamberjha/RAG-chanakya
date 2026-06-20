"""
auth.py
~~~~~~~
JWT authentication layer for the Wings-of-AI backend.

Provides:
  - verify_password(plain, stored_hash)  – matches seed.py's SHA-256 scheme
  - create_access_token(data)            – mints a signed JWT
  - require_auth                         – FastAPI dependency: any valid token
  - require_admin                        – FastAPI dependency: role == 'admin'

JWT configuration (via .env / environment variables):
  JWT_SECRET        – signing secret  (REQUIRED in production; has an insecure default)
  JWT_ALGORITHM     – default HS256
  JWT_EXPIRE_MINUTES – default 60
"""

import hashlib
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# ── Configuration ─────────────────────────────────────────────────────────────
JWT_SECRET: str = os.environ.get(
    "JWT_SECRET", "CHANGE_ME_before_production_wings_of_ai_secret"
)
JWT_ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES: int = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))

_DB_PATH: str = os.environ.get(
    "DB_PATH", os.path.join(os.path.dirname(__file__), "chats.db")
)

# HTTPBearer extracts "Authorization: Bearer <token>" automatically.
# auto_error=False lets us return a 401 with a custom message instead of 403.
_bearer = HTTPBearer(auto_error=False)


# ── Password helpers ──────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    """
    SHA-256 + fixed salt – must match the scheme used in seed.py.
    Keep both in sync if you ever migrate to bcrypt/argon2.
    """
    salt = "wai$salt$"
    return hashlib.sha256((salt + plain).encode()).hexdigest()


def verify_password(plain: str, stored_hash: str) -> bool:
    """Return True if *plain* hashes to *stored_hash*."""
    return _hash_password(plain) == stored_hash


# ── Token helpers ─────────────────────────────────────────────────────────────

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Mint a signed JWT containing *data* plus an 'exp' claim.

    Args:
        data:          Payload dict, e.g. {"sub": "1", "role": "admin"}.
        expires_delta: Override the default expiry window.

    Returns:
        Encoded JWT string.
    """
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=JWT_EXPIRE_MINUTES)
    )
    payload["exp"] = expire
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    """
    Decode and verify a JWT.  Raises HTTPException on any failure.
    """
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Database lookup ───────────────────────────────────────────────────────────

def _get_user_by_id(user_id: int) -> Optional[dict]:
    """Fetch a user row from SQLite by primary key.  Returns None if absent."""
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, email, role, tenant_id FROM users WHERE id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_credential(login: str) -> Optional[dict]:
    """
    Fetch a user by username OR email (used during login).
    Returns a dict with all columns including *password_hash*.
    """
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, email, password_hash, role, tenant_id
        FROM users
        WHERE username = ? OR email = ?
        LIMIT 1
        """,
        (login, login),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ── FastAPI dependency guards ─────────────────────────────────────────────────

def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """
    FastAPI dependency – any authenticated user.

    Injects the current user dict into the route handler:
        async def my_route(user = Depends(require_auth)):
            print(user["role"])

    Raises 401 if token is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing 'sub'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = _get_user_by_id(int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_admin(user: dict = Depends(require_auth)) -> dict:
    """
    FastAPI dependency – admin users only.

    Chains on top of require_auth; raises 403 for non-admin roles.

        async def admin_route(user = Depends(require_admin)):
            ...
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[dict]:
    """
    FastAPI dependency – returns the current user dict if a valid Bearer token
    is present, otherwise returns ``None`` (does NOT raise).

    Use on endpoints that should work both authenticated and anonymously but
    whose behaviour changes based on identity (e.g. retrieval visibility).

        async def my_route(user = Depends(get_optional_user)):
            user_id = user["id"] if user else None
    """
    if credentials is None:
        return None
    try:
        return require_auth(credentials=credentials)
    except HTTPException:
        return None
