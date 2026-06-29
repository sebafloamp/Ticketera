from tests.helpers import login, register_first_admin


def test_register_first_user_becomes_admin(client, db_session):
    response = register_first_admin(client)
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"

    from app.models import User

    user = db_session.query(User).filter(User.email == "admin@example.com").first()
    assert user.role == "admin"


def test_register_second_time_redirects_to_login(client, db_session):
    register_first_admin(client)
    response = register_first_admin(client, email="other@example.com")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_with_wrong_password_returns_401(client, db_session):
    register_first_admin(client)
    response = login(client, "admin@example.com", "wrongpassword")
    assert response.status_code == 401


def test_login_with_correct_password_redirects_to_dashboard(client, db_session):
    register_first_admin(client)
    response = login(client, "admin@example.com", "adminpass123")
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_logout_clears_session(client, db_session):
    register_first_admin(client)
    page = client.get("/dashboard")
    from tests.helpers import _extract_csrf

    token = _extract_csrf(page.text)
    client.post("/logout", data={"csrf_token": token})
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 401
