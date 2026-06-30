from datetime import datetime

from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.csrf import require_csrf
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Period, User

router = APIRouter(prefix="/periods")


@router.post("")
def create_period(
    name: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    period = Period(
        owner_id=current_user.id,
        name=name,
        start_date=datetime.fromisoformat(start_date),
        end_date=datetime.fromisoformat(end_date),
        is_active=True,
    )
    db.add(period)
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
