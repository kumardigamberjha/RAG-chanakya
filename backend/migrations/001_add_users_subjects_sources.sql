-- Migration 001: Add users.role, subjects table, sources table
-- Idempotent: uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS patterns

-- ── 1. Users table ─────────────────────────────────────────────────────────
-- The existing application uses a tenant-based model without a users table.
-- We create one now; existing tenant flows are untouched.
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT    NOT NULL UNIQUE,
    email      TEXT    NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role       TEXT    NOT NULL DEFAULT 'student'
                       CHECK(role IN ('admin', 'student')),
    tenant_id  TEXT,
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ── 2. Subjects table ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subjects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ── 3. Sources table ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sources (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    owner_id   INTEGER          REFERENCES users(id)    ON DELETE SET NULL,
    title      TEXT    NOT NULL,
    file_ref   TEXT    NOT NULL,
    visibility TEXT    NOT NULL DEFAULT 'private'
                       CHECK(visibility IN ('global', 'private')),
    status     TEXT    NOT NULL DEFAULT 'pending',
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ── 4. Indexes ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_sources_subject_id ON sources(subject_id);
CREATE INDEX IF NOT EXISTS idx_sources_owner_id   ON sources(owner_id);
CREATE INDEX IF NOT EXISTS idx_users_tenant_id    ON users(tenant_id);
