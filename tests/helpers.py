import re


def _extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return match.group(1) if match else ""


def register_first_admin(client, email="admin@example.com", password="adminpass123", name="Admin"):
    page = client.get("/register")
    token = _extract_csrf(page.text)
    return client.post(
        "/register",
        data={"email": email, "name": name, "password": password, "csrf_token": token},
        follow_redirects=False,
    )


def login(client, email, password):
    page = client.get("/login")
    token = _extract_csrf(page.text)
    return client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": token},
        follow_redirects=False,
    )


def get_csrf_token(client, get_url):
    page = client.get(get_url)
    return _extract_csrf(page.text)
