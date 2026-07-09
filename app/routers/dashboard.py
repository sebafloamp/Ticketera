from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

from app.csrf import get_or_create_csrf_token
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Period, Project, User, period_participants
from app.progress import (
    calculate_individual_progress,
    calculate_period_progress,
    calculate_project_progress,
)
from app.templating import templates

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    periods = (
        db.query(Period)
        .options(selectinload(Period.projects).selectinload(Project.tickets))
        .filter(Period.owner_id == current_user.id, Period.is_joint.is_(False))
        .order_by(Period.start_date.desc())
        .all()
    )
    joint_periods = (
        db.query(Period)
        .options(selectinload(Period.projects).selectinload(Project.tickets))
        .join(period_participants, period_participants.c.period_id == Period.id)
        .filter(Period.is_joint.is_(True), period_participants.c.user_id == current_user.id)
        .order_by(Period.start_date.desc())
        .all()
    )
    progress = {
        project.id: calculate_project_progress(project)
        for period in periods
        for project in period.projects
    }
    period_progress = {period.id: calculate_period_progress(period) for period in periods}
    joint_progress = {
        period.id: {
            "group": calculate_period_progress(period),
            "mine": calculate_individual_progress(period, current_user),
        }
        for period in joint_periods
    }
    other_users = db.query(User).filter(User.id != current_user.id).order_by(User.name).all()
    token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "periods": periods,
            "joint_periods": joint_periods,
            "progress": progress,
            "period_progress": period_progress,
            "joint_progress": joint_progress,
            "other_users": other_users,
            "current_user": current_user,
            "is_admin": current_user.role == "admin",
            "csrf_token": token,
        },
    )
