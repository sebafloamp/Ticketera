from tests.helpers import _extract_csrf, register_first_admin


def _create_project(client, db_session):
    register_first_admin(client)
    dashboard = client.get("/dashboard")
    token = _extract_csrf(dashboard.text)
    client.post(
        "/periods",
        data={"name": "Q1 2026", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": token},
    )
    from app.models import Period

    period = db_session.query(Period).filter(Period.name == "Q1 2026").first()
    dashboard = client.get("/dashboard")
    token = _extract_csrf(dashboard.text)
    client.post("/projects", data={"period_id": period.id, "title": "Cliente X", "csrf_token": token})

    from app.models import Project

    return db_session.query(Project).filter(Project.title == "Cliente X").first()


def test_create_ticket_appends_with_incrementing_order(client, db_session):
    project = _create_project(client, db_session)
    detail = client.get(f"/projects/{project.id}")
    token = _extract_csrf(detail.text)

    client.post("/tickets", data={"project_id": project.id, "title": "Enviar cotizacion", "priority": "alta", "csrf_token": token})
    client.post("/tickets", data={"project_id": project.id, "title": "Llamar cliente", "priority": "media", "csrf_token": token})

    from app.models import Ticket

    tickets = db_session.query(Ticket).filter(Ticket.project_id == project.id).order_by(Ticket.order).all()
    assert [t.title for t in tickets] == ["Enviar cotizacion", "Llamar cliente"]
    assert [t.order for t in tickets] == [0, 1]
    assert tickets[0].priority == "alta"


def test_move_ticket_updates_status_and_order_and_progress_reflects_it(client, db_session):
    project = _create_project(client, db_session)
    detail = client.get(f"/projects/{project.id}")
    token = _extract_csrf(detail.text)
    client.post("/tickets", data={"project_id": project.id, "title": "Enviar cotizacion", "csrf_token": token})

    from app.models import Ticket

    ticket = db_session.query(Ticket).filter(Ticket.title == "Enviar cotizacion").first()

    board = client.get(f"/projects/{project.id}/board")
    token = _extract_csrf(board.text)
    response = client.post(
        f"/tickets/{ticket.id}/move",
        data={"status": "completado", "order": 0, "csrf_token": token},
    )
    assert response.status_code == 204

    db_session.refresh(ticket)
    assert ticket.status == "completado"

    detail = client.get(f"/projects/{project.id}")
    assert "100.0%" in detail.text


def test_move_ticket_rejects_invalid_status(client, db_session):
    project = _create_project(client, db_session)
    detail = client.get(f"/projects/{project.id}")
    token = _extract_csrf(detail.text)
    client.post("/tickets", data={"project_id": project.id, "title": "Enviar cotizacion", "csrf_token": token})

    from app.models import Ticket

    ticket = db_session.query(Ticket).filter(Ticket.title == "Enviar cotizacion").first()
    board = client.get(f"/projects/{project.id}/board")
    token = _extract_csrf(board.text)
    client.post(f"/tickets/{ticket.id}/move", data={"status": "bogus", "order": 0, "csrf_token": token})

    db_session.refresh(ticket)
    assert ticket.status == "pendiente"


def test_move_ticket_rejects_open_redirect(client, db_session):
    project = _create_project(client, db_session)
    detail = client.get(f"/projects/{project.id}")
    token = _extract_csrf(detail.text)
    client.post("/tickets", data={"project_id": project.id, "title": "Enviar cotizacion", "csrf_token": token})

    from app.models import Ticket

    ticket = db_session.query(Ticket).filter(Ticket.title == "Enviar cotizacion").first()
    board = client.get(f"/projects/{project.id}/board")
    token = _extract_csrf(board.text)
    response = client.post(
        f"/tickets/{ticket.id}/move",
        data={"status": "completado", "order": 0, "csrf_token": token, "redirect_to": "https://evil.example.com/phish"},
        follow_redirects=False,
    )
    assert response.status_code == 204  # falls back to no-redirect response, never follows the external URL


def test_board_endpoint_renders_kanban_by_default_and_list_on_request(client, db_session):
    project = _create_project(client, db_session)
    detail = client.get(f"/projects/{project.id}")
    token = _extract_csrf(detail.text)
    client.post("/tickets", data={"project_id": project.id, "title": "Enviar cotizacion", "csrf_token": token})

    kanban = client.get(f"/projects/{project.id}/board")
    assert "kanban" in kanban.text
    assert "Enviar cotizacion" in kanban.text

    listing = client.get(f"/projects/{project.id}/board?view=list")
    assert "ticket-list" in listing.text
    assert "Enviar cotizacion" in listing.text
