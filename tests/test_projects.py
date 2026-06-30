from tests.helpers import _extract_csrf, register_first_admin


def _create_period(client):
    register_first_admin(client)
    dashboard = client.get("/dashboard")
    token = _extract_csrf(dashboard.text)
    client.post(
        "/periods",
        data={"name": "Q1 2026", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": token},
    )


def test_create_project_under_own_period(client, db_session):
    _create_period(client)
    from app.models import Period

    period = db_session.query(Period).filter(Period.name == "Q1 2026").first()
    dashboard = client.get("/dashboard")
    token = _extract_csrf(dashboard.text)
    response = client.post(
        "/projects",
        data={"period_id": period.id, "title": "Cliente X", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"

    from app.models import Project

    project = db_session.query(Project).filter(Project.title == "Cliente X").first()
    assert project.period_id == period.id


def test_project_detail_shows_progress(client, db_session):
    _create_period(client)
    from app.models import Period

    period = db_session.query(Period).filter(Period.name == "Q1 2026").first()
    dashboard = client.get("/dashboard")
    token = _extract_csrf(dashboard.text)
    client.post("/projects", data={"period_id": period.id, "title": "Cliente X", "csrf_token": token})

    from app.models import Project

    project = db_session.query(Project).filter(Project.title == "Cliente X").first()
    response = client.get(f"/projects/{project.id}")
    assert response.status_code == 200
    assert "Cliente X" in response.text
    assert "0.0%" in response.text


def test_project_detail_404_redirects_for_other_users_project(client, db_session):
    _create_period(client)
    from app.models import Period

    period = db_session.query(Period).filter(Period.name == "Q1 2026").first()
    dashboard = client.get("/dashboard")
    token = _extract_csrf(dashboard.text)
    client.post("/projects", data={"period_id": period.id, "title": "Cliente X", "csrf_token": token})
    from app.models import Project

    project = db_session.query(Project).filter(Project.title == "Cliente X").first()

    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/logout", data={"csrf_token": token})

    from app.auth import hash_password
    from app.models import User
    from tests.helpers import login

    other = User(email="other@example.com", name="Other", password_hash=hash_password("otherpass123"), role="member")
    db_session.add(other)
    db_session.commit()
    login(client, "other@example.com", "otherpass123")

    response = client.get(f"/projects/{project.id}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
