from datetime import datetime

import pytest

from tests.helpers import _extract_csrf, register_first_admin


def test_run_reminders_rejects_missing_config(client, monkeypatch):
    monkeypatch.delenv("REMINDER_TASK_TOKEN", raising=False)
    response = client.post("/internal/reminders/run", headers={"Authorization": "Bearer whatever"})
    assert response.status_code == 503


def test_run_reminders_rejects_wrong_token(client, monkeypatch):
    monkeypatch.setenv("REMINDER_TASK_TOKEN", "correct-token")
    response = client.post("/internal/reminders/run", headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 401


def test_run_reminders_rejects_missing_header(client, monkeypatch):
    monkeypatch.setenv("REMINDER_TASK_TOKEN", "correct-token")
    response = client.post("/internal/reminders/run")
    assert response.status_code == 401


def test_run_reminders_sends_only_to_users_whose_day_matches_today(client, db_session, monkeypatch):
    monkeypatch.setenv("REMINDER_TASK_TOKEN", "correct-token")

    sent_calls = []
    monkeypatch.setattr(
        "app.routers.reminders.send_email",
        lambda to_email, subject, html: sent_calls.append(to_email),
    )

    register_first_admin(client)
    token = _extract_csrf(client.get("/profile").text)
    today_weekday = datetime.now().weekday()

    # Admin sets their reminder day to today and creates a period with a pending ticket.
    client.post(
        "/profile",
        data={"birth_date": "", "phone": "", "job_title": "", "reminder_day": str(today_weekday), "csrf_token": token},
    )
    dtoken = _extract_csrf(client.get("/dashboard").text)
    client.post(
        "/periods",
        data={"name": "Q1 2026", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": dtoken},
    )
    from app.models import Period, Project, Ticket

    period = db_session.query(Period).filter(Period.name == "Q1 2026").first()
    dtoken = _extract_csrf(client.get("/dashboard").text)
    client.post("/projects", data={"period_id": period.id, "title": "Cliente X", "csrf_token": dtoken})
    project = db_session.query(Project).filter(Project.title == "Cliente X").first()
    db_session.add(Ticket(project_id=project.id, title="Pendiente", status="pendiente", order=0))
    db_session.commit()

    # A second team member with their own period, so the admin's consolidated report has content.
    from app.models import User

    member = User(email="member@example.com", name="Member", password_hash="x", role="member")
    db_session.add(member)
    db_session.flush()
    member_period = Period(
        owner_id=member.id, name="Q1 Member",
        start_date=datetime(2026, 1, 1), end_date=datetime(2026, 3, 31),
    )
    db_session.add(member_period)
    db_session.commit()

    response = client.post("/internal/reminders/run", headers={"Authorization": "Bearer correct-token"})
    assert response.status_code == 200
    body = response.json()

    # Admin gets both their own summary AND the consolidated team report -> 2 emails.
    assert sent_calls.count("admin@example.com") == 2
    assert body["sent"].count("admin@example.com") == 2


def test_run_reminders_skips_users_whose_day_is_not_today(client, db_session, monkeypatch):
    monkeypatch.setenv("REMINDER_TASK_TOKEN", "correct-token")
    sent_calls = []
    monkeypatch.setattr(
        "app.routers.reminders.send_email",
        lambda to_email, subject, html: sent_calls.append(to_email),
    )

    register_first_admin(client)
    today_weekday = datetime.now().weekday()
    other_day = (today_weekday + 1) % 7
    token = _extract_csrf(client.get("/profile").text)
    client.post(
        "/profile",
        data={"birth_date": "", "phone": "", "job_title": "", "reminder_day": str(other_day), "csrf_token": token},
    )

    response = client.post("/internal/reminders/run", headers={"Authorization": "Bearer correct-token"})
    assert response.status_code == 200
    assert response.json() == {"sent": [], "skipped": [], "failed": []}
    assert sent_calls == []


def test_run_reminders_skips_user_with_no_pending_tickets(client, db_session, monkeypatch):
    monkeypatch.setenv("REMINDER_TASK_TOKEN", "correct-token")
    monkeypatch.setattr("app.routers.reminders.send_email", lambda *a, **k: None)

    register_first_admin(client)
    today_weekday = datetime.now().weekday()
    token = _extract_csrf(client.get("/profile").text)
    client.post(
        "/profile",
        data={"birth_date": "", "phone": "", "job_title": "", "reminder_day": str(today_weekday), "csrf_token": token},
    )

    response = client.post("/internal/reminders/run", headers={"Authorization": "Bearer correct-token"})
    body = response.json()
    # No periods/tickets at all -> individual summary skipped, and no other members -> admin consolidated skipped too.
    assert "admin@example.com" in body["skipped"]


def test_run_reminders_reports_failure_without_crashing(client, db_session, monkeypatch):
    monkeypatch.setenv("REMINDER_TASK_TOKEN", "correct-token")

    from app.email_sender import EmailSendError

    def _boom(*args, **kwargs):
        raise EmailSendError("resend down")

    monkeypatch.setattr("app.routers.reminders.send_email", _boom)

    register_first_admin(client)
    today_weekday = datetime.now().weekday()
    token = _extract_csrf(client.get("/profile").text)
    client.post(
        "/profile",
        data={"birth_date": "", "phone": "", "job_title": "", "reminder_day": str(today_weekday), "csrf_token": token},
    )
    dtoken = _extract_csrf(client.get("/dashboard").text)
    client.post(
        "/periods",
        data={"name": "Q1 2026", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": dtoken},
    )
    from app.models import Period, Project, Ticket

    period = db_session.query(Period).filter(Period.name == "Q1 2026").first()
    dtoken = _extract_csrf(client.get("/dashboard").text)
    client.post("/projects", data={"period_id": period.id, "title": "Cliente X", "csrf_token": dtoken})
    project = db_session.query(Project).filter(Project.title == "Cliente X").first()
    db_session.add(Ticket(project_id=project.id, title="Pendiente", status="pendiente", order=0))
    db_session.commit()

    response = client.post("/internal/reminders/run", headers={"Authorization": "Bearer correct-token"})
    assert response.status_code == 200
    assert "admin@example.com" in response.json()["failed"]
