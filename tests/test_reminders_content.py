from datetime import datetime

from app.models import Period, Project, Ticket, User
from app.reminders import build_admin_reminder, build_user_reminder


def _make_period_with_tickets(db_session, owner, statuses):
    period = Period(
        owner_id=owner.id, name="Q1 2026",
        start_date=datetime(2026, 1, 1), end_date=datetime(2026, 3, 31),
    )
    db_session.add(period)
    db_session.flush()
    project = Project(period_id=period.id, title="Cliente X")
    db_session.add(project)
    db_session.flush()
    for i, status in enumerate(statuses):
        db_session.add(Ticket(project_id=project.id, title=f"T{i}", status=status, order=i))
    db_session.commit()
    db_session.refresh(period)
    return period


def _make_user(db_session, email="u@example.com"):
    user = User(email=email, name="Usuario", password_hash="x", role="member")
    db_session.add(user)
    db_session.commit()
    return user


def test_build_user_reminder_returns_none_when_nothing_pending(db_session):
    user = _make_user(db_session)
    period = _make_period_with_tickets(db_session, user, ["completado", "completado"])
    assert build_user_reminder(user, [period]) is None


def test_build_user_reminder_includes_only_pending_and_in_progress(db_session):
    user = _make_user(db_session)
    period = _make_period_with_tickets(db_session, user, ["completado", "pendiente", "en_progreso"])
    result = build_user_reminder(user, [period])
    assert result is not None
    subject, html = result
    assert "Cliente X" in html
    assert "T0" not in html  # completado, excluido
    assert "T1" in html
    assert "T2" in html


def test_build_admin_reminder_returns_none_with_no_periods(db_session):
    assert build_admin_reminder({}) is None


def test_build_admin_reminder_lists_members_with_average(db_session):
    member = _make_user(db_session, email="member@example.com")
    period = _make_period_with_tickets(db_session, member, ["completado", "pendiente"])
    result = build_admin_reminder({member: [period]})
    assert result is not None
    subject, html = result
    assert "member@example.com" in html
    assert "50.0%" in html
