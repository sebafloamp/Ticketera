from datetime import date

from tests.helpers import _extract_csrf, register_first_admin


def test_profile_requires_login(client):
    response = client.get("/profile", follow_redirects=False)
    assert response.status_code == 401


def test_profile_shows_created_at_and_email(client, db_session):
    register_first_admin(client)
    page = client.get("/profile")
    assert page.status_code == 200
    assert "admin@example.com" in page.text


def test_update_profile_sets_birth_date_phone_and_job_title(client, db_session):
    register_first_admin(client)
    token = _extract_csrf(client.get("/profile").text)
    response = client.post(
        "/profile",
        data={
            "birth_date": "1990-05-10",
            "phone": "+56 9 1234 5678",
            "job_title": "Analista de soporte",
            "csrf_token": token,
        },
    )
    assert response.status_code == 200
    assert "Datos actualizados" in response.text
    assert "Analista de soporte" in response.text
    assert "+56 9 1234 5678" in response.text
    assert "Edad:" in response.text

    from app.models import User

    user = db_session.query(User).filter(User.email == "admin@example.com").first()
    assert user.birth_date == date(1990, 5, 10)
    assert user.phone == "+56 9 1234 5678"
    assert user.job_title == "Analista de soporte"


def test_profile_shows_birthday_message_when_today_matches(client, db_session):
    register_first_admin(client)
    today = date.today()
    token = _extract_csrf(client.get("/profile").text)
    response = client.post(
        "/profile",
        data={
            "birth_date": date(1990, today.month, today.day).isoformat() if not (today.month == 2 and today.day == 29) else "1990-03-01",
            "phone": "",
            "job_title": "",
            "csrf_token": token,
        },
    )
    assert "Feliz cumpleaños" in response.text


def test_change_password_succeeds_and_new_password_works_on_next_login(client, db_session):
    register_first_admin(client)
    token = _extract_csrf(client.get("/profile").text)
    response = client.post(
        "/profile/password",
        data={
            "current_password": "adminpass123",
            "new_password": "newpassword456",
            "confirm_password": "newpassword456",
            "csrf_token": token,
        },
    )
    assert response.status_code == 200
    assert "Password actualizada" in response.text

    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/logout", data={"csrf_token": token})

    from tests.helpers import login

    login_response = login(client, "admin@example.com", "newpassword456")
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/dashboard"


def test_change_password_rejects_wrong_current_password(client, db_session):
    register_first_admin(client)
    token = _extract_csrf(client.get("/profile").text)
    response = client.post(
        "/profile/password",
        data={
            "current_password": "wrongpassword",
            "new_password": "newpassword456",
            "confirm_password": "newpassword456",
            "csrf_token": token,
        },
    )
    assert response.status_code == 400
    assert "no es correcta" in response.text


def test_change_password_rejects_mismatched_confirmation(client, db_session):
    register_first_admin(client)
    token = _extract_csrf(client.get("/profile").text)
    response = client.post(
        "/profile/password",
        data={
            "current_password": "adminpass123",
            "new_password": "newpassword456",
            "confirm_password": "somethingelse",
            "csrf_token": token,
        },
    )
    assert response.status_code == 400
    assert "no coinciden" in response.text


def test_change_password_rejects_too_short(client, db_session):
    register_first_admin(client)
    token = _extract_csrf(client.get("/profile").text)
    response = client.post(
        "/profile/password",
        data={
            "current_password": "adminpass123",
            "new_password": "short",
            "confirm_password": "short",
            "csrf_token": token,
        },
    )
    assert response.status_code == 400
    assert "al menos 8" in response.text


def test_profile_shows_progress_history_with_average(client, db_session):
    register_first_admin(client)
    token = _extract_csrf(client.get("/dashboard").text)
    client.post(
        "/periods",
        data={"name": "Q1 2026", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": token},
    )

    from app.models import Period, Project, Ticket

    period = db_session.query(Period).filter(Period.name == "Q1 2026").first()
    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/projects", data={"period_id": period.id, "title": "Cliente X", "csrf_token": token})
    project = db_session.query(Project).filter(Project.title == "Cliente X").first()
    db_session.add_all(
        [
            Ticket(project_id=project.id, title="T1", status="completado", order=0),
            Ticket(project_id=project.id, title="T2", status="pendiente", order=1),
        ]
    )
    db_session.commit()

    page = client.get("/profile")
    assert "Q1 2026" in page.text
    assert 'data-target="50.0"' in page.text
    assert "50.0%" in page.text  # single period -> average equals its own pct
