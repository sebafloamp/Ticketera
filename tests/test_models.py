# tests/test_models.py
from datetime import datetime

from app.models import Period, Project, Ticket, User


def test_create_user_period_project_ticket(db_session):
    user = User(email="a@a.com", name="A", password_hash="x", role="member")
    db_session.add(user)
    db_session.flush()

    period = Period(
        owner_id=user.id,
        name="Q1 2026",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 3, 31),
    )
    db_session.add(period)
    db_session.flush()

    project = Project(period_id=period.id, title="Cliente X", description="")
    db_session.add(project)
    db_session.flush()

    ticket = Ticket(
        project_id=project.id,
        title="Enviar cotizacion",
        status="pendiente",
        priority="alta",
        order=0,
    )
    db_session.add(ticket)
    db_session.flush()
    db_session.refresh(project)

    assert project.tickets == [ticket]
    assert period.projects == [project]
    assert ticket.status == "pendiente"


def test_user_role_defaults_to_member(db_session):
    user = User(email="b@b.com", name="B", password_hash="x")
    db_session.add(user)
    db_session.flush()
    assert user.role == "member"
