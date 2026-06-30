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
