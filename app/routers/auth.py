from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.csrf import get_or_create_csrf_token, require_csrf, validate_csrf_token
from app.database import get_db
from app.models import User
from app.rate_limit import limiter
from app.templating import templates

router = APIRouter()

MIN_PASSWORD_LENGTH = 8


def _any_user_exists(db: Session) -> bool:
    return db.query(User).first() is not None


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request, db: Session = Depends(get_db)):
    if _any_user_exists(db):
        return RedirectResponse("/login", status_code=303)
    token = get_or_create_csrf_token(request)
    return templates.TemplateResponse("register.html", {"request": request, "csrf_token": token, "error": None})


@router.post("/register")
@limiter.limit("5/minute")
def register_submit(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    if _any_user_exists(db):
        return RedirectResponse("/login", status_code=303)
    if not validate_csrf_token(request, csrf_token):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "csrf_token": get_or_create_csrf_token(request), "error": "Token invalido, reintenta."},
            status_code=400,
        )
    if len(password) < MIN_PASSWORD_LENGTH:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "csrf_token": get_or_create_csrf_token(request),
                "error": f"La password debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.",
            },
            status_code=400,
        )

    user = User(email=email, name=name, password_hash=hash_password(password), role="admin")
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "csrf_token": get_or_create_csrf_token(request), "error": "El email ya existe."},
            status_code=400,
        )

    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    token = get_or_create_csrf_token(request)
    return templates.TemplateResponse("login.html", {"request": request, "csrf_token": token, "error": None})


@router.post("/login")
@limiter.limit("5/minute")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    if not validate_csrf_token(request, csrf_token):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "csrf_token": get_or_create_csrf_token(request), "error": "Token invalido, reintenta."},
            status_code=400,
        )

    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "csrf_token": get_or_create_csrf_token(request), "error": "Email o password incorrectos."},
            status_code=401,
        )

    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/logout")
def logout(request: Request, _: None = Depends(require_csrf)):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
