import sqlite3
import os
from typing import Optional

_DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "chats.db"))


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON;")
    return c


# ── Subjects ──────────────────────────────────────────────────────────────────

def subject_list() -> list[dict]:
    """Return all subjects ordered by name."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, name, description, created_at FROM subjects ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]


def subject_create(name: str, description: Optional[str] = None) -> dict:
    """
    Insert a new subject.  Raises ValueError on duplicate name.
    Returns the created row as a dict.
    """
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO subjects (name, description) VALUES (?, ?)",
                (name, description),
            )
            row = conn.execute(
                "SELECT id, name, description, created_at FROM subjects WHERE name = ?",
                (name,),
            ).fetchone()
        return dict(row)
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Subject '{name}' already exists.") from exc


def subject_get(subject_id: int) -> Optional[dict]:
    """Return a single subject by PK, or None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, name, description, created_at FROM subjects WHERE id = ?",
            (subject_id,),
        ).fetchone()
    return dict(row) if row else None


def subject_delete(subject_id: int) -> bool:
    """
    Delete a subject by PK.  Returns True if a row was deleted.
    All linked sources are cascade-deleted by the FK constraint.
    """
    with _conn() as conn:
        cur = conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
    return cur.rowcount > 0
