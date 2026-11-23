"""
Product data model (Phase B): users (admin/student), batches, attendance.

Do databases kyun?
- Biometric store (`store/db.py`): sirf face embeddings, encrypted, audit-logged. Minimum data.
- Product DB (yahan): naam, email, phone, batch, attendance. SQLAlchemy -> SQLite (dev) ya
  Postgres (prod, Phase E) bina code badle.
Dono `users.person_id` se jude hain. Biometric data ko baaki app data se alag rakhna privacy ka
standard pattern hai: product DB leak ho to bhi chehre ka data usmein nahi.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    # Local time (settings.timezone) mein "HH:MM". Attendance window isi se nikalti hai.
    start_time: Mapped[str] = mapped_column(String(5))
    end_time: Mapped[str] = mapped_column(String(5))
    days: Mapped[str] = mapped_column(String(20), default="0,1,2,3,4")  # Mon=0 .. Sun=6
    late_after_min: Mapped[int] = mapped_column(Integer, default=10)
    open_before_min: Mapped[int] = mapped_column(Integer, default=15)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    students: Mapped[list[User]] = relationship(back_populates="batch")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10), default="student")  # admin | student
    full_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20))
    roll_no: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(10), default="active")  # active | inactive
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("batches.id", ondelete="SET NULL"))
    # Biometric store ka person id (face enroll ke baad set hota hai)
    person_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    enrollment_date: Mapped[date] = mapped_column(Date, default=lambda: _now().date())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Password change / logout-all pe badhao -> purane JWT invalid
    token_version: Mapped[int] = mapped_column(Integer, default=0)

    batch: Mapped[Batch | None] = relationship(back_populates="students")


class Attendance(Base):
    __tablename__ = "attendance"
    # Ek student, ek batch, ek din = ek record (duplicate prevention DB level pe)
    __table_args__ = (UniqueConstraint("user_id", "batch_id", "day", name="uq_attendance_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)  # local date (settings.timezone)
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    status: Mapped[str] = mapped_column(String(10))  # present | late | absent
    method: Mapped[str] = mapped_column(String(10))  # face | manual
    confidence: Mapped[float | None] = mapped_column(Float)  # face similarity
    marked_by: Mapped[str] = mapped_column(String(64))  # "self" | admin user id | "kiosk"

    user: Mapped[User] = relationship()
    batch: Mapped[Batch] = relationship()


def make_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite mein foreign keys default OFF hoti hain
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys = ON")
            cur.close()

    return engine


def make_sessionmaker(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_all(engine: Engine) -> None:
    """Dev/test ke liye. Prod (Postgres) mein Alembic migrations (Phase E)."""
    Base.metadata.create_all(engine)
