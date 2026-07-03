from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.csrf import get_or_create_csrf_token, require_csrf
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Period, Project, Ticket, User
from app.progress import calculate_project_progress
from app.templating import templates

router = APIRouter()

VALID_STATUSES = ("pendiente", "en_progreso", "completado")


def _safe_redirect_target(redirect_to):
    if not redirect_to:
        return None
    if redirect_to.startswith("/") and not redirect_to.startswith("//"):
        return redirect_to
    return None


def _project_for_user(db: Session, project_id: int, user_id: int):
    return (
        db.query(Project)
        .join(Period)
        .filter(Project.id == project_id, Period.owner_id == user_id)
        .first()
    )


def _ticket_for_user(db: Session, ticket_id: int, user_id: int):
    return (
        db.query(Ticket)
        .join(Project)
        .join(Period)
        .filter(Ticket.id == ticket_id, Period.owner_id == user_id)
        .first()
    )


@router.post("/tickets")
def create_ticket(
    project_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    priority: str = Form("media"),
    due_date: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    project = _project_for_user(db, project_id, current_user.id)
    if project:
        max_order = db.query(func.max(Ticket.order)).filter(Ticket.project_id == project.id).scalar()
        max_order = max_order if max_order is not None else -1
        db.add(
            Ticket(
                project_id=project.id,
                title=title,
                description=description,
                status="pendiente",
                priority=priority if priority in ("alta", "media", "baja") else "media",
                due_date=datetime.fromisoformat(due_date) if due_date else None,
                order=max_order + 1,
            )
        )
        db.commit()
    return RedirectResponse(f"/projects/{project_id}", status_code=303)


@router.post("/tickets/{ticket_id}/delete")
def delete_ticket(
    ticket_id: int,
    redirect_to: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    ticket = _ticket_for_user(db, ticket_id, current_user.id)
    if not ticket:
        return RedirectResponse("/dashboard", status_code=303)
    project_id = ticket.project_id
    db.delete(ticket)
    db.commit()
    safe_redirect = _safe_redirect_target(redirect_to)
    return RedirectResponse(safe_redirect or f"/projects/{project_id}", status_code=303)


@router.post("/tickets/{ticket_id}/move")
def move_ticket(
    ticket_id: int,
    status: str = Form(...),
    order: int = Form(0),
    redirect_to: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    safe_redirect = _safe_redirect_target(redirect_to)

    if status not in VALID_STATUSES:
        return RedirectResponse(safe_redirect, status_code=303) if safe_redirect else Response(status_code=204)

    ticket = _ticket_for_user(db, ticket_id, current_user.id)
    if not ticket:
        return RedirectResponse(safe_redirect, status_code=303) if safe_redirect else Response(status_code=204)

    ticket.status = status
    ticket.order = order
    db.commit()

    if safe_redirect:
        return RedirectResponse(safe_redirect, status_code=303)
    return Response(status_code=204)


@router.get("/projects/{project_id}/board", response_class=HTMLResponse)
def project_board(
    project_id: int,
    request: Request,
    view: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _project_for_user(db, project_id, current_user.id)
    if not project:
        return RedirectResponse("/dashboard", status_code=303)

    selected_view = view if view in ("kanban", "list") else request.session.get("ticket_view", "kanban")
    request.session["ticket_view"] = selected_view

    tickets_sorted = sorted(project.tickets, key=lambda ticket: ticket.order)
    token = get_or_create_csrf_token(request)
    template_name = "partials/kanban_board.html" if selected_view == "kanban" else "partials/ticket_list.html"
    return templates.TemplateResponse(
        template_name,
        {
            "request": request,
            "project": project,
            "tickets": tickets_sorted,
            "csrf_token": token,
        },
    )
