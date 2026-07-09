from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.authz import user_can_access_period
from app.csrf import get_or_create_csrf_token, require_csrf
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Project, Ticket, User
from app.templating import templates

router = APIRouter()

VALID_STATUSES = ("pendiente", "en_progreso", "completado")


def _safe_redirect_target(redirect_to):
    if not redirect_to:
        return None
    if redirect_to.startswith("/") and not redirect_to.startswith("//"):
        return redirect_to
    return None


def _project_for_user(db: Session, project_id: int, user: User):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project and user_can_access_period(project.period, user):
        return project
    return None


def _ticket_for_user(db: Session, ticket_id: int, user: User):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if ticket and user_can_access_period(ticket.project.period, user):
        return ticket
    return None


@router.post("/tickets")
def create_ticket(
    project_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    priority: str = Form("media"),
    due_date: str = Form(""),
    assignee_ids: list[int] = Form([]),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    project = _project_for_user(db, project_id, current_user)
    if project:
        assignees = []
        if project.period.is_joint:
            # Solo participantes del periodo pueden ser responsables, y es obligatorio elegir al menos uno.
            participants_by_id = {p.id: p for p in project.period.participants}
            assignees = [participants_by_id[uid] for uid in dict.fromkeys(assignee_ids) if uid in participants_by_id]
            if not assignees:
                return Response("Debes asignar al menos un responsable.", status_code=400)
        max_order = db.query(func.max(Ticket.order)).filter(Ticket.project_id == project.id).scalar()
        max_order = max_order if max_order is not None else -1
        ticket = Ticket(
            project_id=project.id,
            title=title,
            description=description.strip()[:100],
            status="pendiente",
            priority=priority if priority in ("alta", "media", "baja") else "media",
            due_date=datetime.fromisoformat(due_date) if due_date else None,
            order=max_order + 1,
        )
        ticket.assignees = assignees
        db.add(ticket)
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
    ticket = _ticket_for_user(db, ticket_id, current_user)
    if not ticket:
        return RedirectResponse("/dashboard", status_code=303)
    project_id = ticket.project_id
    db.delete(ticket)
    db.commit()
    safe_redirect = _safe_redirect_target(redirect_to)
    return RedirectResponse(safe_redirect or f"/projects/{project_id}", status_code=303)


@router.post("/tickets/{ticket_id}/edit")
def edit_ticket(
    ticket_id: int,
    description: str = Form(""),
    redirect_to: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
):
    safe_redirect = _safe_redirect_target(redirect_to)
    ticket = _ticket_for_user(db, ticket_id, current_user)
    if ticket:
        ticket.description = description.strip()[:100]
        db.commit()
    if safe_redirect:
        return RedirectResponse(safe_redirect, status_code=303)
    return Response(status_code=204)


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

    ticket = _ticket_for_user(db, ticket_id, current_user)
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
    project = _project_for_user(db, project_id, current_user)
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
