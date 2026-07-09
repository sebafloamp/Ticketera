from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


period_participants = Table(
    "period_participants",
    Base.metadata,
    Column("period_id", Integer, ForeignKey("periods.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
)

ticket_assignees = Table(
    "ticket_assignees",
    Base.metadata,
    Column("ticket_id", Integer, ForeignKey("tickets.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="member")  # "admin" | "member"
    birth_date = Column(Date, nullable=True)
    phone = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    reminder_day = Column(Integer, nullable=True)  # 0=lunes .. 6=domingo, None=sin recordatorio
    created_at = Column(DateTime, default=utcnow)


class Period(Base):
    __tablename__ = "periods"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    is_joint = Column(Boolean, nullable=False, default=False)  # True = periodo conjunto con participantes

    projects = relationship("Project", back_populates="period", cascade="all, delete-orphan")
    participants = relationship("User", secondary=period_participants)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    period_id = Column(Integer, ForeignKey("periods.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)

    period = relationship("Period", back_populates="projects")
    tickets = relationship("Ticket", back_populates="project", cascade="all, delete-orphan")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    status = Column(String, nullable=False, default="pendiente")  # "pendiente" | "en_progreso" | "completado"
    priority = Column(String, nullable=False, default="media")  # "alta" | "media" | "baja"
    due_date = Column(DateTime, nullable=True)
    order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="tickets")
    assignees = relationship("User", secondary=ticket_assignees)
