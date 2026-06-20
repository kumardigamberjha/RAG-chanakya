"""
seed.py
~~~~~~~
Seed script – creates one admin user in the database.

Run from the backend/ directory:

    # Using the project venv
    python seed.py

    # Or with uv
    uv run python seed.py

The script is idempotent: it will NOT create a duplicate if the admin
user already exists (identified by username AND email).

Environment variables (optional, fall back to safe defaults):
    DB_PATH        – path to chats.db   (default: ./chats.db)
    ADMIN_USERNAME – admin account name  (default: admin)
    ADMIN_EMAIL    – admin e-mail        (default: admin@wingsofai.local)
    ADMIN_PASSWORD – plain-text password (default: changeme123!)

WARNING: change the default password before deploying to production.
"""

import os
import sys
import hashlib
import sqlite3

# ── Configuration (override via env vars) ────────────────────────────────────
DB_PATH        = os.environ.get("DB_PATH",        os.path.join(os.path.dirname(__file__), "chats.db"))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL",    "admin@wingsofai.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

STUDENT_TENANT    = os.environ.get("STUDENT_TENANT", "school-alpha-01")
STUDENT_PASSWORD  = os.environ.get("STUDENT_PASSWORD", "student123!")
STUDENTS = [
    {"username": "student_a", "email": "student_a@school.local"},
    {"username": "student_b", "email": "student_b@school.local"},
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _hash_password(plain: str) -> str:
    """
    Minimal password hashing with SHA-256 + a fixed salt prefix.

    Replace with bcrypt / argon2 before production use.
    """
    salt = "wai$salt$"   # constant for reproducibility in a seed context
    return hashlib.sha256((salt + plain).encode()).hexdigest()


# ── Ensure migration is applied first ────────────────────────────────────────
def _run_migrations() -> None:
    """Apply any pending SQL migrations so the users table exists."""
    try:
        # migrate.py lives in the same directory as seed.py
        sys.path.insert(0, os.path.dirname(__file__))
        from migrate import run_migrations
        run_migrations(DB_PATH)
    except Exception as exc:
        print(f"[seed] WARNING: could not run migrations automatically: {exc}")
        print("[seed] Continuing – assuming tables already exist.")


# ── Seed ──────────────────────────────────────────────────────────────────────
def seed() -> None:
    _run_migrations()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # Check if admin already exists
    cursor.execute(
        "SELECT id, username, email, role FROM users WHERE username = ? OR email = ?",
        (ADMIN_USERNAME, ADMIN_EMAIL),
    )
    existing = cursor.fetchone()

    password_hash = _hash_password(ADMIN_PASSWORD)

    if existing:
        print(
            f"[seed] Admin user already exists – updating password.\n"
            f"       id={existing[0]}  username={existing[1]}  "
            f"email={existing[2]}  role={existing[3]}"
        )
        cursor.execute(
            "UPDATE users SET password_hash = ?, role = 'admin' WHERE id = ?",
            (password_hash, existing[0])
        )
        conn.commit()
        conn.close()
        return

    cursor.execute(
        """
        INSERT INTO users (username, email, password_hash, role)
        VALUES (?, ?, ?, 'admin')
        """,
        (ADMIN_USERNAME, ADMIN_EMAIL, password_hash),
    )
    conn.commit()

    cursor.execute("SELECT id, username, email, role, created_at FROM users WHERE username = ?", (ADMIN_USERNAME,))
    row = cursor.fetchone()
    conn.close()

    print("[seed] ✓ Admin user created successfully.")
    print(f"       id         : {row[0]}")
    print(f"       username   : {row[1]}")
    print(f"       email      : {row[2]}")
    print(f"       role       : {row[3]}")
    print(f"       created_at : {row[4]}")
    print(f"       password   : {ADMIN_PASSWORD}  ← change this before production!")


def seed_students() -> None:
    """Idempotently create student_a and student_b for acceptance testing."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    password_hash = _hash_password(STUDENT_PASSWORD)

    for s in STUDENTS:
        cursor.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (s["username"], s["email"]),
        )
        if cursor.fetchone():
            print(f"[seed] Student '{s['username']}' already exists – skipping.")
            continue

        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash, role, tenant_id)
            VALUES (?, ?, ?, 'student', ?)
            """,
            (s["username"], s["email"], password_hash, STUDENT_TENANT),
        )
        conn.commit()

        cursor.execute("SELECT id FROM users WHERE username = ?", (s["username"],))
        row = cursor.fetchone()
        print(f"[seed] ✓ Student '{s['username']}' created (id={row[0]}, tenant={STUDENT_TENANT}).")

    conn.close()


if __name__ == "__main__":
    seed()
    seed_students()
