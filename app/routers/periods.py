from datetime import datetime

from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.csrf import require_csrf
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Period, Project, Ticket, User

router = APIRouter(prefix="/periods")

PENDING_STATUSES = ("pendiente", "en_progreso")


def _carry_over_pending(db: Session, previous: Period, new_period: Period) -> None:
    """Copia al periodo nuevo los proyectos del anterior que tengan tickets sin completar.

    Los tickets completados nunca se copian, asi que un ticket resuelto deja de
    propagarse a periodos futuros. El periodo anterior queda intacto (duplicacion
    deliberada: registra lo que no se termino en su momento).
    """
    for project in previous.projects:
        pending = [t for t in project.tickets if t.status in PENDING_STATUSES]
        if not pending:
            continue
        new_project = Project(period_id=new_period.id, title=project.title)
        db.add(new_project)
        db.flush()
        for order, ticket in enumerate(sorted(pending, key=lambda t: t.order)):
            db.add(
                Ticket(
                    project_id=new_project.id,
                    title=ticket.title,
                    description=ticket.description,
                    status=ticket.status,
                    priority=ticket.priority,
                    due_date=ticket.due_date,
                    order=order,
                )
            )


@router.post("")
def create_period(
    name: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    carry_over: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    new_start = datetime.fromisoformat(start_date)
    previous = (
        db.query(Period)
        .filter(Period.owner_id == current_user.id)
        .order_by(Period.start_date.desc())
        .first()
    )

    period = Period(
        owner_id=current_user.id,
        name=name,
        start_date=new_start,
        end_date=datetime.fromisoformat(end_date),
        is_active=True,
    )
    db.add(period)
    db.flush()

    if carry_over and previous and new_start > previous.start_date:
        _carry_over_pending(db, previous, period)

    db.commit()
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/{period_id}/delete")
def delete_period(
    period_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    period = db.query(Period).filter(Period.id == period_id, Period.owner_id == current_user.id).first()
    if period:
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
