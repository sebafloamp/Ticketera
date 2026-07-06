from tests.helpers import _extract_csrf, register_first_admin


def test_dashboard_requires_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 401


def test_create_period_scopes_to_current_user(client, db_session):
    register_first_admin(client)
    dashboard = client.get("/dashboard")
    token = _extract_csrf(dashboard.text)
    response = client.post(
        "/periods",
        data={"name": "Q1 2026", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303

    from app.models import Period, User

    user = db_session.query(User).filter(User.email == "admin@example.com").first()
    period = db_session.query(Period).filter(Period.name == "Q1 2026").first()
    assert period.owner_id == user.id

    dashboard = client.get("/dashboard")
    assert "Q1 2026" in dashboard.text


def test_close_period_only_affects_owners_own_period(client, db_session):
    register_first_admin(client)
    dashboard = client.get("/dashboard")
    token = _extract_csrf(dashboard.text)
    client.post(
        "/periods",
        data={"name": "Q1 2026", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": token},
    )

    from app.models import Period

    period = db_session.query(Period).filter(Period.name == "Q1 2026").first()
    dashboard = client.get("/dashboard")
    token = _extract_csrf(dashboard.text)
    client.post(f"/periods/{period.id}/close", data={"csrf_token": token})

    db_session.refresh(period)
    assert period.is_active is False


def test_close_period_blocked_for_non_owner(client, db_session):
    register_first_admin(client)
    dashboard = client.get("/dashboard")
    token = _extract_csrf(dashboard.text)
    client.post(
        "/periods",
        data={"name": "Q1 2026", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": token},
    )

    from app.models import Period

    period = db_session.query(Period).filter(Period.name == "Q1 2026").first()

    # Log out admin, log in as a different user
    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/logout", data={"csrf_token": token})

    from app.auth import hash_password
    from app.models import User
    from tests.helpers import login

    other = User(email="other@example.com", name="Other", password_hash=hash_password("otherpass123"), role="member")
    db_session.add(other)
    db_session.commit()
    login(client, "other@example.com", "otherpass123")

    # Attempt to close admin's period as the other user
    other_dashboard = client.get("/dashboard")
    token = _extract_csrf(other_dashboard.text)
    client.post(f"/periods/{period.id}/close", data={"csrf_token": token})

    db_session.refresh(period)
    assert period.is_active is True  # still active — other user cannot close it


def _seed_period_with_tickets(client, db_session):
    """Q1 with one project holding a pendiente, an en_progreso, and a completado ticket."""
    register_first_admin(client)
    token = _extract_csrf(client.get("/dashboard").text)
    client.post(
        "/periods",
        data={"name": "Q1 2026", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": token},
    )
    from app.models import Period, Project, Ticket

    q1 = db_session.query(Period).filter(Period.name == "Q1 2026").first()
    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/projects", data={"period_id": q1.id, "title": "Cliente X", "csrf_token": token})
    project = db_session.query(Project).filter(Project.title == "Cliente X").first()
    db_session.add_all(
        [
            Ticket(project_id=project.id, title="Pendiente 1", status="pendiente", priority="alta", order=0),
            Ticket(project_id=project.id, title="En progreso 1", status="en_progreso", priority="media", order=1),
            Ticket(project_id=project.id, title="Hecho 1", status="completado", priority="baja", order=2),
        ]
    )
    db_session.commit()
    return q1, project


def test_new_period_carries_over_pending_tickets(client, db_session):
    from app.models import Period, Project, Ticket

    q1, old_project = _seed_period_with_tickets(client, db_session)

    token = _extract_csrf(client.get("/dashboard").text)
    client.post(
        "/periods",
        data={
            "name": "Q2 2026", "start_date": "2026-04-01", "end_date": "2026-06-30",
            "carry_over": "1", "csrf_token": token,
        },
    )

    q2 = db_session.query(Period).filter(Period.name == "Q2 2026").first()
    copied = db_session.query(Project).filter(Project.period_id == q2.id, Project.title == "Cliente X").first()
    assert copied is not None

    titles = {t.title: t.status for t in db_session.query(Ticket).filter(Ticket.project_id == copied.id).all()}
    assert titles == {"Pendiente 1": "pendiente", "En progreso 1": "en_progreso"}  # completado no viaja

    # El periodo viejo queda intacto (duplicacion deliberada)
    assert db_session.query(Ticket).filter(Ticket.project_id == old_project.id).count() == 3


def test_carry_over_skipped_when_new_period_starts_earlier(client, db_session):
    from app.models import Period, Project

    _seed_period_with_tickets(client, db_session)

    token = _extract_csrf(client.get("/dashboard").text)
    client.post(
        "/periods",
        data={
            "name": "Q0 2025", "start_date": "2025-10-01", "end_date": "2025-12-31",
            "carry_over": "1", "csrf_token": token,
        },
    )

    q0 = db_session.query(Period).filter(Period.name == "Q0 2025").first()
    assert q0 is not None  # el periodo se crea igual
    assert db_session.query(Project).filter(Project.period_id == q0.id).count() == 0  # sin arrastre


def test_carry_over_skipped_when_checkbox_unchecked(client, db_session):
    from app.models import Period, Project

    _seed_period_with_tickets(client, db_session)

    token = _extract_csrf(client.get("/dashboard").text)
    client.post(
        "/periods",
        data={"name": "Q2 2026", "start_date": "2026-04-01", "end_date": "2026-06-30", "csrf_token": token},
    )

    q2 = db_session.query(Period).filter(Period.name == "Q2 2026").first()
    assert db_session.query(Project).filter(Project.period_id == q2.id).count() == 0


def test_resolved_carryover_ticket_does_not_travel_to_third_period(client, db_session):
    from app.models import Period, Project, Ticket

    _seed_period_with_tickets(client, db_session)

    token = _extract_csrf(client.get("/dashboard").text)
    client.post(
        "/periods",
        data={
            "name": "Q2 2026", "start_date": "2026-04-01", "end_date": "2026-06-30",
            "carry_over": "1", "csrf_token": token,
        },
    )

    q2 = db_session.query(Period).filter(Period.name == "Q2 2026").first()
    q2_project = db_session.query(Project).filter(Project.period_id == q2.id).first()
    for ticket in db_session.query(Ticket).filter(Ticket.project_id == q2_project.id).all():
        ticket.status = "completado"
    db_session.commit()

    token = _extract_csrf(client.get("/dashboard").text)
    client.post(
        "/periods",
        data={
            "name": "Q3 2026", "start_date": "2026-07-01", "end_date": "2026-09-30",
            "carry_over": "1", "csrf_token": token,
        },
    )

    q3 = db_session.query(Period).filter(Period.name == "Q3 2026").first()
    assert db_session.query(Project).filter(Project.period_id == q3.id).count() == 0  # todo resuelto, nada viaja
