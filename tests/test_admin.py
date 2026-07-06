import re

from tests.helpers import _extract_csrf, login, register_first_admin


def _invite_member(client, email="member@example.com", name="Member"):
    page = client.get("/admin")
    token = _extract_csrf(page.text)
    response = client.post(
        "/admin/invite",
        data={"name": name, "email": email, "csrf_token": token},
    )
    temp_password = re.search(r"<code>([^<]+)</code>", response.text).group(1)
    return temp_password


def test_admin_page_requires_admin_role(client, db_session):
    register_first_admin(client)
    temp_password = _invite_member(client)

    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/logout", data={"csrf_token": token})
    login(client, "member@example.com", temp_password)

    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 403


def test_admin_can_invite_member_with_temp_password(client, db_session):
    register_first_admin(client)
    temp_password = _invite_member(client)

    from app.auth import verify_password
    from app.models import User

    user = db_session.query(User).filter(User.email == "member@example.com").first()
    assert user is not None
    assert user.role == "member"
    assert verify_password(temp_password, user.password_hash)


def test_admin_dashboard_shows_aggregate_ticket_counts_across_members(client, db_session):
    register_first_admin(client)
    temp_password = _invite_member(client)

    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/logout", data={"csrf_token": token})
    login(client, "member@example.com", temp_password)

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
    client.post("/projects", data={"period_id": period.id, "title": "Cliente X", "csrf_token": token})
    from app.models import Project

    project = db_session.query(Project).filter(Project.title == "Cliente X").first()
    detail = client.get(f"/projects/{project.id}")
    token = _extract_csrf(detail.text)
    client.post("/tickets", data={"project_id": project.id, "title": "Enviar cotizacion", "csrf_token": token})

    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/logout", data={"csrf_token": token})
    login(client, "admin@example.com", "adminpass123")

    admin_page = client.get("/admin")
    assert "member@example.com" in admin_page.text
    assert "1" in admin_page.text


def test_admin_can_view_members_periods_readonly(client, db_session):
    register_first_admin(client)
    temp_password = _invite_member(client)

    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/logout", data={"csrf_token": token})
    login(client, "member@example.com", temp_password)
    dashboard = client.get("/dashboard")
    token = _extract_csrf(dashboard.text)
    client.post(
        "/periods",
        data={"name": "Q1 2026", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": token},
    )

    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/logout", data={"csrf_token": token})
    login(client, "admin@example.com", "adminpass123")

    from app.models import User

    member = db_session.query(User).filter(User.email == "member@example.com").first()
    response = client.get(f"/admin/users/{member.id}")
    assert response.status_code == 200
    assert "Q1 2026" in response.text
    assert "<form" not in response.text


def _seed_member_with_period(client, db_session, temp_password):
    """As the invited member: one period, one project, 1 completado + 1 pendiente ticket."""
    from app.models import Period, Project, Ticket, User

    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/logout", data={"csrf_token": token})
    login(client, "member@example.com", temp_password)

    token = _extract_csrf(client.get("/dashboard").text)
    client.post(
        "/periods",
        data={"name": "Q1 2026", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": token},
    )
    period = db_session.query(Period).filter(Period.name == "Q1 2026").first()
    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/projects", data={"period_id": period.id, "title": "Cliente X", "csrf_token": token})
    project = db_session.query(Project).filter(Project.title == "Cliente X").first()
    db_session.add_all(
        [
            Ticket(project_id=project.id, title="Hecho", status="completado", order=0),
            Ticket(project_id=project.id, title="Falta", status="pendiente", order=1),
        ]
    )
    db_session.commit()

    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/logout", data={"csrf_token": token})
    login(client, "admin@example.com", "adminpass123")
    return period


def test_admin_dashboard_shows_user_progress_bar(client, db_session):
    register_first_admin(client)
    temp_password = _invite_member(client)
    _seed_member_with_period(client, db_session, temp_password)

    page = client.get("/admin")
    assert page.status_code == 200
    # 1 of 2 tickets done in the only project of the only period -> 50.0%
    assert 'data-target="50.0"' in page.text
    assert "50.0%" in page.text


def test_admin_user_view_shows_period_progress_and_counts(client, db_session):
    from app.models import User

    register_first_admin(client)
    temp_password = _invite_member(client)
    _seed_member_with_period(client, db_session, temp_password)

    member = db_session.query(User).filter(User.email == "member@example.com").first()
    page = client.get(f"/admin/users/{member.id}")
    assert page.status_code == 200
    assert 'data-target="50.0"' in page.text
    assert "Pendiente: 1" in page.text
    assert "En progreso: 0" in page.text
    assert "Completado: 1" in page.text


def test_admin_can_invite_new_admin_and_they_can_access_admin_panel(client, db_session):
    register_first_admin(client)

    page = client.get("/admin")
    token = _extract_csrf(page.text)
    response = client.post(
        "/admin/invite",
        data={"name": "Segundo Admin", "email": "admin2@example.com", "role": "admin", "csrf_token": token},
    )
    temp_password = re.search(r"<code>([^<]+)</code>", response.text).group(1)

    from app.models import User

    new_admin = db_session.query(User).filter(User.email == "admin2@example.com").first()
    assert new_admin.role == "admin"

    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/logout", data={"csrf_token": token})
    login(client, "admin2@example.com", temp_password)

    admin_page = client.get("/admin")
    assert admin_page.status_code == 200


def test_admin_dashboard_lists_all_other_participants_regardless_of_role(client, db_session):
    register_first_admin(client)

    page = client.get("/admin")
    token = _extract_csrf(page.text)
    client.post(
        "/admin/invite",
        data={"name": "Segundo Admin", "email": "admin2@example.com", "role": "admin", "csrf_token": token},
    )
    _invite_member(client, email="member2@example.com", name="Member Two")

    admin_page = client.get("/admin")
    assert "admin2@example.com" in admin_page.text
    assert "member2@example.com" in admin_page.text


def test_invalid_role_value_defaults_to_member(client, db_session):
    register_first_admin(client)

    page = client.get("/admin")
    token = _extract_csrf(page.text)
    client.post(
        "/admin/invite",
        data={"name": "Raro", "email": "raro@example.com", "role": "superadmin", "csrf_token": token},
    )

    from app.models import User

    user = db_session.query(User).filter(User.email == "raro@example.com").first()
    assert user.role == "member"
