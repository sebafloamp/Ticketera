from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.birthday import calculate_age, is_birthday_today
from app.csrf import get_or_create_csrf_token, require_csrf
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Period, User
from app.progress import calculate_period_progress, calculate_user_progress
from app.templating import templates

router = APIRouter(prefix="/profile")

MIN_PASSWORD_LENGTH = 8


def _profile_context(request: Request, db: Session, current_user: User, error=None, success=None):
    periods = (
        db.query(Period)
        .filter(Period.owner_id == current_user.id)
        .order_by(Period.start_date.desc())
        .all()
    )
    period_progress = [(period, calculate_period_progress(period)) for period in periods]
    progress_average = calculate_user_progress(periods)

    today = datetime.now().date()
    age = calculate_age(current_user.birth_date, today) if current_user.birth_date else None
    birthday_today = is_birthday_today(current_user.birth_date, today) if current_user.birth_date else False

    return {
        "request": request,
        "user": current_user,
        "age": age,
        "birthday_today": birthday_today,
        "period_progress": period_progress,
        "progress_average": progress_average,
        "csrf_token": get_or_create_csrf_token(request),
        "error": error,
        "success": success,
    }


@router.get("", response_class=HTMLResponse)
def profile_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse("profile.html", _profile_context(request, db, current_user))


@router.post("", response_class=HTMLResponse)
def update_profile(
    request: Request,
    birth_date: str = Form(""),
    phone: str = Form(""),
    job_title: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    if birth_date:
        try:
            current_user.birth_date = date.fromisoformat(birth_date)
        except ValueError:
            return templates.TemplateResponse(
                "profile.html",
                _profile_context(request, db, current_user, error="Fecha de nacimiento invalida."),
                status_code=400,
            )
    else:
        current_user.birth_date = None

    current_user.phone = phone.strip()[:30] or None
    current_user.job_title = job_title.strip()[:100] or None
    db.commit()

    return templates.TemplateResponse(
        "profile.html",
        _profile_context(request, db, current_user, success="Datos actualizados."),
    )


@router.post("/password", response_class=HTMLResponse)
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    if not verify_password(current_password, current_user.password_hash):
        return templates.TemplateResponse(
            "profile.html",
            _profile_context(request, db, current_user, error="La password actual no es correcta."),
            status_code=400,
        )
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "profile.html",
            _profile_context(request, db, current_user, error="Las passwords nuevas no coinciden."),
            status_code=400,
        )
    if len(new_password) < MIN_PASSWORD_LENGTH:
        return templates.TemplateResponse(
            "profile.html",
            _profile_context(
                request, db, current_user,
                error=f"La password nueva debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.",
            ),
            status_code=400,
        )

    current_user.password_hash = hash_password(new_password)
    db.commit()

    return templates.TemplateResponse(
        "profile.html",
        _profile_context(request, db, current_user, success="Password actualizada."),
    )
