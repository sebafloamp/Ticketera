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
