from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.authz import user_can_access_period
from app.csrf import get_or_create_csrf_token, require_csrf
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Period, Project, Ticket, User
from app.progress import (
    calculate_individual_progress,
    calculate_period_progress,
    calculate_project_progress,
)
from app.templating import templates

router = APIRouter(prefix="/periods")

PENDING_STATUSES = ("pendiente", "en_progreso")


def _carry_over_pending(db: Session, previous: Period, new_period: Period) -> None:
    """Copia al periodo nuevo los proyectos del anterior que tengan tickets sin completar.

    Los tickets completados nunca se copian, asi que un ticket resuelto deja de
    propagarse a periodos futuros. El periodo anterior queda intacto (duplicacion
    deliberada: registra lo que no se termino en su momento). En periodos conjuntos
    los tickets copiados conservan sus responsables.
    """
    for project in previous.projects:
        pending = [t for t in project.tickets if t.status in PENDING_STATUSES]
        if not pending:
            continue
        new_project = Project(period_id=new_period.id, title=project.title)
        db.add(new_project)
        db.flush()
        for order, ticket in enumerate(sorted(pending, key=lambda t: t.order)):
            new_ticket = Ticket(
                project_id=new_project.id,
                title=ticket.title,
                description=ticket.description,
                status=ticket.status,
                priority=ticket.priority,
                due_date=ticket.due_date,
                order=order,
            )
            new_ticket.assignees = list(ticket.assignees)
            db.add(new_ticket)


@router.post("")
def create_period(
    name: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    carry_over: str = Form(""),
    is_joint: str = Form(""),
    participant_ids: list[int] = Form([]),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    joint = bool(is_joint)
    new_start = datetime.fromisoformat(start_date)
    # El carry-over no mezcla tipos: un periodo conjunto solo arrastra del
    # ultimo periodo conjunto del mismo creador, y un personal solo de personales.
    previous = (
        db.query(Period)
        .filter(Period.owner_id == current_user.id, Period.is_joint == joint)
        .order_by(Period.start_date.desc())
        .first()
    )

    period = Period(
        owner_id=current_user.id,
        name=name,
        start_date=new_start,
        end_date=datetime.fromisoformat(end_date),
        is_active=True,
        is_joint=joint,
    )
    db.add(period)
    db.flush()

    if joint:
        participants = [current_user]
        if participant_ids:
            others = (
                db.query(User)
                .filter(User.id.in_(participant_ids), User.id != current_user.id)
                .all()
            )
            participants.extend(others)
        period.participants = participants

    if carry_over and previous and new_start > previous.start_date:
        _carry_over_pending(db, previous, period)

    db.commit()
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/{period_id}", response_class=HTMLResponse)
def period_detail(
    period_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    period = db.query(Period).filter(Period.id == period_id).first()
    if not period or not period.is_joint:
        return RedirectResponse("/dashboard", status_code=303)
    if not user_can_access_period(period, current_user):
        raise HTTPException(status_code=403, detail="No participas de este periodo")

    project_progress = {project.id: calculate_project_progress(project) for project in period.projects}
    individual_progress = [
        (participant, calculate_individual_progress(period, participant))
        for participant in sorted(period.participants, key=lambda u: u.name)
    ]
    token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        "joint_period_detail.html",
        {
            "request": request,
            "period": period,
            "group_progress": calculate_period_progress(period),
            "project_progress": project_progress,
            "individual_progress": individual_progress,
            "current_user": current_user,
            "csrf_token": token,
        },
    )


@router.post("/{period_id}/delete")
def delete_period(
    period_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    # Eliminar sigue siendo exclusivo del creador, incluso en periodos conjuntos.
    period = db.query(Period).filter(Period.id == period_id, Period.owner_id == current_user.id).first()
    if period:
        period.participants = []
        db.delete(period)
        db.commit()
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/{period_id}/close")
def close_period(
    period_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    period = db.query(Period).filter(Period.id == period_id, Period.owner_id == current_user.id).first()
    if period:
        period.is_active = False
        db.commit()
    return RedirectResponse("/dashboard", status_code=303)
