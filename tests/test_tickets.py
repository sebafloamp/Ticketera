from app.models import Period, Project, Ticket
from tests.helpers import _extract_csrf, register_first_admin


def _create_project(client, db_session):
    register_first_admin(client)
    dashboard = client.get("/dashboard")
    token = _extract_csrf(dashboard.text)
    client.post(
        "/periods",
        data={"name": "Q1 2026", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": token},
    )
    period = db_session.query(Period).filter(Period.name == "Q1 2026").first()
    dashboard = client.get("/dashboard")
    token = _extract_csrf(dashboard.text)
    client.post("/projects", data={"period_id": period.id, "title": "Cliente X", "csrf_token": token})
    return db_session.query(Project).filter(Project.title == "Cliente X").first()


def test_create_ticket_appends_with_incrementing_order(client, db_session):
    project = _create_project(client, db_session)
    detail = client.get(f"/projects/{project.id}")
    token = _extract_csrf(detail.text)

    client.post("/tickets", data={"project_id": project.id, "title": "Enviar cotizacion", "priority": "alta", "csrf_token": token})
    client.post("/tickets", data={"project_id": project.id, "title": "Llamar cliente", "priority": "media", "csrf_token": token})

    tickets = db_session.query(Ticket).filter(Ticket.project_id == project.id).order_by(Ticket.order).all()
    assert [t.title for t in tickets] == ["Enviar cotizacion", "Llamar cliente"]
    assert [t.order for t in tickets] == [0, 1]
    assert tickets[0].priority == "alta"


def test_move_ticket_updates_status_and_order_and_progress_reflects_it(client, db_session):
    project = _create_project(client, db_session)
    detail = client.get(f"/projects/{project.id}")
    token = _extract_csrf(detail.text)
    client.post("/tickets", data={"project_id": project.id, "title": "Enviar cotizacion", "csrf_token": token})

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

    ticket = db_session.query(Ticket).filter(Ticket.title == "Enviar cotizacion").first()
    board = client.get(f"/projects/{project.id}/board")
    token = _extract_csrf(board.text)
    response = client.post(
        f"/tickets/{ticket.id}/move",
        data={"status": "completado", "order": 0, "csrf_token": token, "redirect_to": "https://evil.example.com/phish"},
        follow_redirects=False,
    )
    assert response.status_code == 204


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

    # session persistence: next request without ?view= should still return list
    listing2 = client.get(f"/projects/{project.id}/board")
    assert "ticket-list" in listing2.text


def test_delete_ticket_removes_it_and_redirects_to_project(client, db_session):
    project = _create_project(client, db_session)
    detail = client.get(f"/projects/{project.id}")
    token = _extract_csrf(detail.text)
    client.post("/tickets", data={"project_id": project.id, "title": "Borrable", "csrf_token": token})
    ticket = db_session.query(Ticket).filter(Ticket.title == "Borrable").first()

    response = client.post(
        f"/tickets/{ticket.id}/delete",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/projects/{project.id}"
    assert db_session.query(Ticket).filter(Ticket.id == ticket.id).first() is None


def test_delete_project_cascades_tickets(client, db_session):
    project = _create_project(client, db_session)
    detail = client.get(f"/projects/{project.id}")
    token = _extract_csrf(detail.text)
    client.post("/tickets", data={"project_id": project.id, "title": "Hijo", "csrf_token": token})

    response = client.post(
        f"/projects/{project.id}/delete",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert db_session.query(Project).filter(Project.id == project.id).first() is None
    assert db_session.query(Ticket).filter(Ticket.project_id == project.id).count() == 0


def test_delete_period_cascades_projects_and_tickets(client, db_session):
    project = _create_project(client, db_session)
    period_id = project.period_id
    detail = client.get(f"/projects/{project.id}")
    token = _extract_csrf(detail.text)
    client.post("/tickets", data={"project_id": project.id, "title": "Nieto", "csrf_token": token})

    response = client.post(
        f"/periods/{period_id}/delete",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert db_session.query(Period).filter(Period.id == period_id).first() is None
    assert db_session.query(Project).count() == 0
    assert db_session.query(Ticket).count() == 0
