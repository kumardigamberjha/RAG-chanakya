"""
models.py
~~~~~~~~~
SQLAlchemy ORM model declarations for the Wings-of-AI backend.

These models map 1-to-1 to the tables created by migration
001_add_users_subjects_sources.sql and extend the pre-existing
`chats` / `messages` tables (which remain raw-sqlite in database.py).

Usage (read-only introspection / future CRUD layer):
    from models import User, Subject, Source, UserRole, Visibility, get_session

    session = get_session()
    admin = session.query(User).filter_by(role=UserRole.admin).first()
    session.close()

The module deliberately avoids touching `database.py` or `migrate.py`
so that no existing behaviour is altered.
"""

import enum
import os
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

# ── Database path (mirrors the value used in database.py / migrate.py) ──────
_DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "chats.db")
DB_URL = f"sqlite:///{os.environ.get('DB_PATH', _DEFAULT_DB_PATH)}"


# ── Base ─────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Enums ────────────────────────────────────────────────────────────────────
class UserRole(str, enum.Enum):
    admin = "admin"
    student = "student"


class Visibility(str, enum.Enum):
    global_ = "global"   # stored as 'global' in DB
    private = "private"


# ── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    """
    Application user.

    role: 'admin' | 'student'  (CHECK constraint mirrors the SQL migration)
    tenant_id: optional link to the legacy tenant-based isolation layer.
    """
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    username      = Column(String, nullable=False, unique=True)
    email         = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    role          = Column(
        Enum(UserRole, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=UserRole.student,
    )
    tenant_id  = Column(String, nullable=True)
    created_at = Column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    # Relationships
    sources = relationship("Source", back_populates="owner", foreign_keys="Source.owner_id")

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'student')", name="ck_users_role"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role}>"


class Subject(Base):
    """
    An academic subject / course that groups Sources together.
    """
    __tablename__ = "subjects"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at  = Column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    # Relationships
    sources = relationship("Source", back_populates="subject", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Subject id={self.id} name={self.name!r}>"


class Source(Base):
    """
    A document / file source associated with a Subject.

    subject_id  : FK → subjects.id  (required)
    owner_id    : FK → users.id     (nullable – system-owned sources have no owner)
    file_ref    : opaque path / object-key for the stored file
    visibility  : 'global' | 'private'
    status      : free-text lifecycle state (e.g. 'pending', 'indexed', 'failed')
    """
    __tablename__ = "sources"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    owner_id   = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title      = Column(String, nullable=False)
    file_ref   = Column(String, nullable=False)
    visibility = Column(
        Enum(Visibility, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=Visibility.private,
    )
    status     = Column(String, nullable=False, default="pending")
    created_at = Column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    # Relationships
    subject = relationship("Subject", back_populates="sources")
    owner   = relationship("User", back_populates="sources", foreign_keys=[owner_id])

    __table_args__ = (
        CheckConstraint("visibility IN ('global', 'private')", name="ck_sources_visibility"),
        Index("idx_sources_subject_id_orm", "subject_id"),
        Index("idx_sources_owner_id_orm",   "owner_id"),
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id} title={self.title!r} visibility={self.visibility}>"


# ── Session factory (lazy-initialised) ───────────────────────────────────────

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            DB_URL,
            connect_args={"check_same_thread": False},  # safe for SQLite + threads
            echo=False,
        )
    return _engine


def get_session():
    """
    Return a new SQLAlchemy Session bound to the application database.

    Callers are responsible for closing the session when done:
        session = get_session()
        try:
            ...
        finally:
            session.close()
    """
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal()
