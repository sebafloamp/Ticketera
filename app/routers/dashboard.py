from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.csrf import get_or_create_csrf_token
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Period, Project, User
from sqlalchemy.orm import selectinload
from app.progress import calculate_project_progress
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
        .filter(Period.owner_id == current_user.id)
        .order_by(Period.start_date.desc())
        .all()
    )
    progress = {
        project.id: calculate_project_progress(project)
        for period in periods
        for project in period.projects
    }
    token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "periods": periods,
            "progress": progress,
            "is_admin": current_user.role == "admin",
            "csrf_token": token,
        },
    )
