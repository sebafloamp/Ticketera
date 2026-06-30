from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.csrf import get_or_create_csrf_token, require_csrf
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Period, Project, User
from app.progress import calculate_project_progress
from app.templating import templates

router = APIRouter(prefix="/projects")


@router.post("")
def create_project(
    period_id: int = Form(...),
    title: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    period = db.query(Period).filter(Period.id == period_id, Period.owner_id == current_user.id).first()
    if period:
        db.add(Project(period_id=period.id, title=title))
        db.commit()
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/{project_id}", response_class=HTMLResponse)
def project_detail(
    project_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = (
        db.query(Project)
        .join(Period)
        .filter(Project.id == project_id, Period.owner_id == current_user.id)
        .first()
    )
    if not project:
        return RedirectResponse("/dashboard", status_code=303)

    token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        "project_detail.html",
        {
            "request": request,
            "project": project,
            "project_progress": calculate_project_progress(project),
            "csrf_token": token,
        },
    )
