import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.csrf import get_or_create_csrf_token, require_csrf
from app.database import get_db
from app.dependencies import require_admin
from app.models import Period, Project, Ticket, User
from app.progress import calculate_period_progress, calculate_project_progress, calculate_user_progress
from app.templating import templates

router = APIRouter(prefix="/admin")


def _ticket_counts_by_status(db: Session, member_id: int) -> dict:
    rows = (
        db.query(Ticket.status)
        .join(Project)
        .join(Period)
        .filter(Period.owner_id == member_id)
        .all()
    )
    counts = {"pendiente": 0, "en_progreso": 0, "completado": 0}
    for (status,) in rows:
        counts[status] = counts.get(status, 0) + 1
    return counts


def _user_progress(db: Session, member_id: int) -> float:
    periods = db.query(Period).filter(Period.owner_id == member_id).all()
    return calculate_user_progress(periods)


def _period_ticket_counts(period: Period) -> dict:
    counts = {"pendiente": 0, "en_progreso": 0, "completado": 0}
    for project in period.projects:
        for ticket in project.tickets:
            counts[ticket.status] = counts.get(ticket.status, 0) + 1
    return counts


def _other_participants(db: Session, admin_user: User):
    return db.query(User).filter(User.id != admin_user.id).order_by(User.name).all()


@router.get("", response_class=HTMLResponse)
def admin_dashboard(request: Request, admin_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    members = _other_participants(db, admin_user)
    counts = {member.id: _ticket_counts_by_status(db, member.id) for member in members}
    user_progress = {member.id: _user_progress(db, member.id) for member in members}
    token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        "admin_dashboard.html",
        {"request": request, "members": members, "counts": counts, "user_progress": user_progress, "csrf_token": token, "temp_password": None, "error": None},
    )


@router.post("/invite", response_class=HTMLResponse)
def invite_member(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
    role: str = Form("member"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    safe_role = role if role in ("admin", "member") else "member"
    temp_password = secrets.token_urlsafe(8)
    user = User(email=email, name=name, password_hash=hash_password(temp_password), role=safe_role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        members = _other_participants(db, admin_user)
        counts = {member.id: _ticket_counts_by_status(db, member.id) for member in members}
        user_progress = {member.id: _user_progress(db, member.id) for member in members}
        token = get_or_create_csrf_token(request)
        return templates.TemplateResponse(
            "admin_dashboard.html",
            {"request": request, "members": members, "counts": counts, "user_progress": user_progress, "csrf_token": token, "temp_password": None, "error": "Ese email ya esta registrado."},
            status_code=400,
        )

    members = _other_participants(db, admin_user)
    counts = {member.id: _ticket_counts_by_status(db, member.id) for member in members}
    user_progress = {member.id: _user_progress(db, member.id) for member in members}
    token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        "admin_dashboard.html",
        {"request": request, "members": members, "counts": counts, "user_progress": user_progress, "csrf_token": token, "temp_password": temp_password, "error": None},
    )


@router.get("/users/{user_id}", response_class=HTMLResponse)
def admin_user_periods(
    user_id: int,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    member = db.query(User).filter(User.id == user_id, User.id != admin_user.id).first()
    if not member:
        return RedirectResponse("/admin", status_code=303)

    periods = db.query(Period).filter(Period.owner_id == member.id).order_by(Period.start_date.desc()).all()
    progress = {project.id: calculate_project_progress(project) for period in periods for project in period.projects}
    period_progress = {period.id: calculate_period_progress(period) for period in periods}
    period_counts = {period.id: _period_ticket_counts(period) for period in periods}
    return templates.TemplateResponse(
        "admin_user_periods.html",
        {
            "request": request,
            "member": member,
            "periods": periods,
            "progress": progress,
            "period_progress": period_progress,
            "period_counts": period_counts,
        },
    )


@router.get("/users/{user_id}/projects/{project_id}", response_class=HTMLResponse)
def admin_project_tickets(
    user_id: int,
    project_id: int,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    member = db.query(User).filter(User.id == user_id, User.id != admin_user.id).first()
    if not member:
        return RedirectResponse("/admin", status_code=303)

    project = (
        db.query(Project)
        .join(Period)
        .filter(Project.id == project_id, Period.owner_id == member.id)
        .first()
    )
    if not project:
        return RedirectResponse(f"/admin/users/{user_id}", status_code=303)

    tickets_sorted = sorted(project.tickets, key=lambda ticket: ticket.order)
    return templates.TemplateResponse(
        "admin_project_tickets.html",
        {"request": request, "member": member, "project": project, "tickets": tickets_sorted},
    )
