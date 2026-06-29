import hmac
import secrets

from fastapi import Form, HTTPException, Request

CSRF_SESSION_KEY = "csrf_token"


def get_or_create_csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


def validate_csrf_token(request: Request, submitted_token: str) -> bool:
    expected = request.session.get(CSRF_SESSION_KEY, "")
    if not expected or not submitted_token:
        return False
    return hmac.compare_digest(expected, submitted_token)


def require_csrf(request: Request, csrf_token: str = Form(...)) -> None:
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=400, detail="Token CSRF invalido")
