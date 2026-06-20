import sqlite3
import os
from typing import Optional

_DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "chats.db"))


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON;")
    return c


# ── Sources ───────────────────────────────────────────────────────────────────

def source_create(
    subject_id: int,
    title: str,
    file_ref: str,
    *,
    owner_id: Optional[int] = None,
    visibility: str = "private",
    status: str = "pending",
) -> dict:
    """
    Insert a new source record.  Returns the created row as a dict.

    For admin-uploaded global files call with:
        owner_id=None, visibility='global'
    """
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO sources (subject_id, owner_id, title, file_ref, visibility, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (subject_id, owner_id, title, file_ref, visibility, status),
        )
        row = conn.execute(
            """
            SELECT id, subject_id, owner_id, title, file_ref, visibility, status, created_at
            FROM sources
            WHERE rowid = last_insert_rowid()
            """,
        ).fetchone()
    return dict(row)


def source_get(source_id: int) -> Optional[dict]:
    """Return a single source by PK, or None."""
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT id, subject_id, owner_id, title, file_ref, visibility, status, created_at
            FROM   sources WHERE id = ?
            """,
            (source_id,),
        ).fetchone()
    return dict(row) if row else None


def source_delete(source_id: int) -> bool:
    """Delete a source row by PK. Returns True if a row was deleted."""
    with _conn() as conn:
        cur = conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    return cur.rowcount > 0


def source_update_status(source_id: int, status: str) -> bool:
    """Update the status field of a source (e.g. 'pending' → 'ready' | 'failed')."""
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE sources SET status = ? WHERE id = ?",
            (status, source_id),
        )
    return cur.rowcount > 0


def source_list_by_subject(subject_id: int) -> list[dict]:
    """Return all sources for a given subject, newest first."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, subject_id, owner_id, title, file_ref, visibility, status, created_at
            FROM   sources
            WHERE  subject_id = ?
            ORDER  BY created_at DESC
            """,
            (subject_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def source_list_for_user(subject_id: int, user_id: Optional[int]) -> list[dict]:
    """Return sources visible to a student: global ones + their own private ones (if authenticated)."""
    with _conn() as conn:
        if user_id is None:
            rows = conn.execute(
                """
                SELECT id, subject_id, owner_id, title, file_ref, visibility, status, created_at
                FROM   sources
                WHERE  subject_id = ?
                AND    visibility = 'global'
                ORDER  BY created_at DESC
                """,
                (subject_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, subject_id, owner_id, title, file_ref, visibility, status, created_at
                FROM   sources
                WHERE  subject_id = ?
                AND    (visibility = 'global' OR owner_id = ?)
                ORDER  BY created_at DESC
                """,
                (subject_id, user_id),
            ).fetchall()
    return [dict(r) for r in rows]
