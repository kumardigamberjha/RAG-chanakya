"""
migrate.py
~~~~~~~~~~
Simple migration runner for the RAG backend.

Works alongside the existing raw-sqlite database.py approach:
- Reads *.sql files from the `migrations/` directory in alphabetical order.
- Tracks applied migrations in a `_schema_migrations` table so each file
  is executed exactly once (idempotent re-runs).
- Called automatically from database.init_db() at startup, or manually:

    uv run python migrate.py          # apply pending migrations
    uv run python migrate.py --status # show migration status
"""

import os
import sqlite3
import sys
import glob

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")
DB_PATH = os.environ.get("DB_PATH", "chats.db")


def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _schema_migrations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            filename   TEXT    NOT NULL UNIQUE,
            applied_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )
    """)
    conn.commit()


def _applied_migrations(conn: sqlite3.Connection) -> set:
    rows = conn.execute("SELECT filename FROM _schema_migrations").fetchall()
    return {row[0] for row in rows}


def run_migrations(db_path: str = DB_PATH) -> None:
    """Apply all pending *.sql migrations in the migrations/ directory."""
    conn = _get_conn(db_path)
    _ensure_migrations_table(conn)

    applied = _applied_migrations(conn)

    sql_files = sorted(
        glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))
    )

    if not sql_files:
        print("[migrate] No migration files found in migrations/")
        conn.close()
        return

    pending = [f for f in sql_files if os.path.basename(f) not in applied]

    if not pending:
        print(f"[migrate] All {len(sql_files)} migration(s) already applied. Nothing to do.")
        conn.close()
        return

    for filepath in pending:
        filename = os.path.basename(filepath)
        print(f"[migrate] Applying: {filename} …", end=" ", flush=True)
        with open(filepath, "r", encoding="utf-8") as fh:
            sql = fh.read()
        try:
            conn.executescript(sql)          # executescript auto-commits
            # Record as applied (executescript resets autocommit, re-open txn)
            conn.execute(
                "INSERT INTO _schema_migrations (filename) VALUES (?)",
                (filename,)
            )
            conn.commit()
            print("OK")
        except Exception as exc:
            conn.rollback()
            conn.close()
            print(f"FAILED\n[migrate] Error applying {filename}: {exc}")
            raise SystemExit(1) from exc

    print(f"[migrate] Done. Applied {len(pending)} migration(s).")
    conn.close()


def migration_status(db_path: str = DB_PATH) -> None:
    """Print which migrations have been applied and which are pending."""
    conn = _get_conn(db_path)
    _ensure_migrations_table(conn)
    applied = _applied_migrations(conn)
    conn.close()

    sql_files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
    if not sql_files:
        print("[migrate] No migration files found.")
        return

    print(f"{'Status':<10} Filename")
    print("-" * 50)
    for filepath in sql_files:
        filename = os.path.basename(filepath)
        status = "applied" if filename in applied else "pending"
        print(f"{status:<10} {filename}")


if __name__ == "__main__":
    if "--status" in sys.argv:
        migration_status()
    else:
        run_migrations()
