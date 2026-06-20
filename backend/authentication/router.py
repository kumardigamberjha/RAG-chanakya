from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from authentication.auth import get_user_by_credential, verify_password, create_access_token

router = APIRouter(prefix="/api", tags=["auth"])

class LoginRequest(BaseModel):
    """Body for POST /api/auth/login."""
    login: str    # accepts username OR email
    password: str

@router.post("/auth/login")
async def login(body: LoginRequest):
    """
    Exchange credentials for a signed JWT.

    - **login**: username or email address
    - **password**: plain-text password

    Returns ``{"access_token": "<jwt>", "token_type": "bearer", "role": "<role>"}``.
    Raises **401** on invalid credentials.
    """
    try:
        from db.seed import seed as run_seed, seed_students as run_seed_students
        run_seed()
        run_seed_students()
    except Exception as exc:
        print(f"[login hook] seeding failed: {exc}")

    user = get_user_by_credential(body.login)
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": str(user["id"]), "role": user["role"]})
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}

@router.get("/debug-users")
async def debug_users():
    import sqlite3
    import os
    conn = sqlite3.connect(os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "chats.db")))
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, password_hash, role, tenant_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1], "email": r[2], "password_hash": r[3], "role": r[4], "tenant_id": r[5]} for r in rows]
