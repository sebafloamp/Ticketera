import re

from tests.helpers import _extract_csrf, login, register_first_admin


def _invite_member(client, email="member@example.com", name="Member"):
    page = client.get("/admin")
    token = _extract_csrf(page.text)
    response = client.post(
        "/admin/invite",
        data={"name": name, "email": email, "csrf_token": token},
    )
    temp_password = re.search(r"<code>([^<]+)</code>", response.text).group(1)
    return temp_password


def _logout_and_login(client, email, password):
    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/logout", data={"csrf_token": token})
    login(client, email, password)


def _create_joint_period(client, db_session, participant_ids, name="Conjunto Q1", start="2026-01-01", end="2026-03-31", carry_over=""):
    token = _extract_csrf(client.get("/dashboard").text)
    client.post(
        "/periods",
        data={
            "name": name,
            "start_date": start,
            "end_date": end,
            "is_joint": "1",
            "carry_over": carry_over,
            "csrf_token": token,
            "participant_ids": [str(pid) for pid in participant_ids],
        },
    )
    from app.models import Period

    return db_session.query(Period).filter(Period.name == name).first()


def _setup_admin_member_and_joint_period(client, db_session):
    """Admin registrado + member invitado + periodo conjunto con ambos. Devuelve (member, member_pass, period)."""
    register_first_admin(client)
    temp_password = _invite_member(client)

    from app.models import User

    member = db_session.query(User).filter(User.email == "member@example.com").first()
    period = _create_joint_period(client, db_session, [member.id])
    return member, temp_password, period


def test_create_joint_period_includes_creator_and_selected_participants(client, db_session):
    member, _, period = _setup_admin_member_and_joint_period(client, db_session)

    assert period.is_joint is True
    emails = sorted(p.email for p in period.participants)
    assert emails == ["admin@example.com", "member@example.com"]


def test_personal_period_creation_unchanged(client, db_session):
    register_first_admin(client)
    token = _extract_csrf(client.get("/dashboard").text)
    client.post(
        "/periods",
        data={"name": "Personal Q1", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": token},
    )

    from app.models import Period

    period = db_session.query(Period).filter(Period.name == "Personal Q1").first()
    assert period.is_joint is False
    assert period.participants == []


def test_dashboard_shows_joint_section_with_group_and_individual_progress(client, db_session):
    _setup_admin_member_and_joint_period(client, db_session)

    page = client.get("/dashboard")
    assert "Periodos conjuntos" in page.text
    assert "Progreso Grupal" in page.text
    assert "Progreso individual" in page.text
    assert "Conjunto Q1" in page.text


def test_joint_period_not_duplicated_in_personal_section(client, db_session):
    _setup_admin_member_and_joint_period(client, db_session)

    page = client.get("/dashboard")
    # El nombre aparece solo una vez (seccion conjunta), no en "Mis periodos".
    assert page.text.count("Conjunto Q1") == 2  # titulo del periodo + confirm() del boton eliminar


def test_participant_sees_joint_period_in_dashboard(client, db_session):
    member, temp_password, _ = _setup_admin_member_and_joint_period(client, db_session)
    _logout_and_login(client, "member@example.com", temp_password)

    page = client.get("/dashboard")
    assert "Conjunto Q1" in page.text


def test_joint_period_detail_renders_progress_for_each_participant(client, db_session):
    _, _, period = _setup_admin_member_and_joint_period(client, db_session)

    page = client.get(f"/periods/{period.id}")
    assert page.status_code == 200
    assert "Progreso Grupal" in page.text
    assert "Progreso individual" in page.text
    assert "Member" in page.text
    assert "Admin" in page.text


def test_joint_period_detail_forbidden_for_non_participant(client, db_session):
    _, _, period = _setup_admin_member_and_joint_period(client, db_session)
    temp_password = _invite_member(client, email="outsider@example.com", name="Outsider")
    _logout_and_login(client, "outsider@example.com", temp_password)

    response = client.get(f"/periods/{period.id}")
    assert response.status_code == 403


def test_participant_can_create_project_in_joint_period(client, db_session):
    member, temp_password, period = _setup_admin_member_and_joint_period(client, db_session)
    _logout_and_login(client, "member@example.com", temp_password)

    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/projects", data={"period_id": period.id, "title": "Proyecto del member", "csrf_token": token})

    from app.models import Project

    project = db_session.query(Project).filter(Project.title == "Proyecto del member").first()
    assert project is not None
    assert project.period_id == period.id


def test_non_participant_cannot_create_project_in_joint_period(client, db_session):
    _, _, period = _setup_admin_member_and_joint_period(client, db_session)
    temp_password = _invite_member(client, email="outsider@example.com", name="Outsider")
    _logout_and_login(client, "outsider@example.com", temp_password)

    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/projects", data={"period_id": period.id, "title": "Intruso", "csrf_token": token})

    from app.models import Project

    assert db_session.query(Project).filter(Project.title == "Intruso").first() is None


def _create_project_in_period(client, db_session, period, title="Proyecto conjunto"):
    token = _extract_csrf(client.get("/dashboard").text)
    client.post("/projects", data={"period_id": period.id, "title": title, "csrf_token": token})

    from app.models import Project

    return db_session.query(Project).filter(Project.title == title).first()


def test_ticket_in_joint_project_requires_assignee(client, db_session):
    _, _, period = _setup_admin_member_and_joint_period(client, db_session)
    project = _create_project_in_period(client, db_session, period)

    token = _extract_csrf(client.get(f"/projects/{project.id}").text)
    response = client.post(
        "/tickets",
        data={"project_id": project.id, "title": "Sin responsable", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 400

    from app.models import Ticket

    assert db_session.query(Ticket).filter(Ticket.title == "Sin responsable").first() is None


def test_ticket_in_joint_project_accepts_multiple_assignees(client, db_session):
    member, _, period = _setup_admin_member_and_joint_period(client, db_session)
    project = _create_project_in_period(client, db_session, period)

    from app.models import User

    admin = db_session.query(User).filter(User.email == "admin@example.com").first()
    token = _extract_csrf(client.get(f"/projects/{project.id}").text)
    client.post(
        "/tickets",
        data={
            "project_id": str(project.id),
            "title": "Compartido",
            "csrf_token": token,
            "assignee_ids": [str(admin.id), str(member.id)],
        },
    )

    from app.models import Ticket

    ticket = db_session.query(Ticket).filter(Ticket.title == "Compartido").first()
    assert ticket is not None
    assert sorted(a.email for a in ticket.assignees) == ["admin@example.com", "member@example.com"]


def test_ticket_assignee_outside_participants_is_ignored(client, db_session):
    member, _, period = _setup_admin_member_and_joint_period(client, db_session)
    temp_password = _invite_member(client, email="outsider@example.com", name="Outsider")

    from app.models import User

    outsider = db_session.query(User).filter(User.email == "outsider@example.com").first()
    project = _create_project_in_period(client, db_session, period)
    token = _extract_csrf(client.get(f"/projects/{project.id}").text)
    response = client.post(
        "/tickets",
        data={
            "project_id": str(project.id),
            "title": "Solo intruso",
            "csrf_token": token,
            "assignee_ids": [str(outsider.id)],
        },
        follow_redirects=False,
    )
    # El unico responsable propuesto no participa del periodo -> queda sin responsables validos -> 400.
    assert response.status_code == 400


def test_ticket_in_personal_project_does_not_require_assignee(client, db_session):
    register_first_admin(client)
    token = _extract_csrf(client.get("/dashboard").text)
    client.post(
        "/periods",
        data={"name": "Personal Q1", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": token},
    )

    from app.models import Period, Ticket

    period = db_session.query(Period).filter(Period.name == "Personal Q1").first()
    project = _create_project_in_period(client, db_session, period, title="Proyecto personal")
    token = _extract_csrf(client.get(f"/projects/{project.id}").text)
    client.post("/tickets", data={"project_id": project.id, "title": "Libre", "csrf_token": token})

    ticket = db_session.query(Ticket).filter(Ticket.title == "Libre").first()
    assert ticket is not None
    assert ticket.assignees == []


def test_participant_can_move_ticket_status(client, db_session):
    member, temp_password, period = _setup_admin_member_and_joint_period(client, db_session)
    project = _create_project_in_period(client, db_session, period)

    from app.models import Ticket

    ticket = Ticket(project_id=project.id, title="Movible", status="pendiente", order=0)
    ticket.assignees = [member]
    db_session.add(ticket)
    db_session.commit()

    _logout_and_login(client, "member@example.com", temp_password)
    token = _extract_csrf(client.get(f"/projects/{project.id}").text)
    client.post(f"/tickets/{ticket.id}/move", data={"status": "completado", "order": 0, "csrf_token": token})

    db_session.refresh(ticket)
    assert ticket.status == "completado"


def test_individual_progress_counts_full_ticket_for_each_assignee(client, db_session):
    member, _, period = _setup_admin_member_and_joint_period(client, db_session)
    project = _create_project_in_period(client, db_session, period)

    from app.models import Ticket, User
    from app.progress import calculate_individual_progress

    admin = db_session.query(User).filter(User.email == "admin@example.com").first()
    shared = Ticket(project_id=project.id, title="Compartido", status="completado", order=0)
    shared.assignees = [admin, member]
    solo_admin = Ticket(project_id=project.id, title="Solo admin", status="pendiente", order=1)
    solo_admin.assignees = [admin]
    db_session.add_all([shared, solo_admin])
    db_session.commit()
    db_session.refresh(period)

    # El ticket compartido completado cuenta entero para ambos.
    assert calculate_individual_progress(period, member) == 100.0
    assert calculate_individual_progress(period, admin) == 50.0


def test_individual_progress_zero_when_no_assigned_tickets(client, db_session):
    member, _, period = _setup_admin_member_and_joint_period(client, db_session)

    from app.progress import calculate_individual_progress

    assert calculate_individual_progress(period, member) == 0.0


def test_joint_carry_over_preserves_assignees(client, db_session):
    member, _, period = _setup_admin_member_and_joint_period(client, db_session)
    project = _create_project_in_period(client, db_session, period)

    from app.models import Ticket

    pending = Ticket(project_id=project.id, title="Pendiente conjunto", status="pendiente", order=0)
    pending.assignees = [member]
    done = Ticket(project_id=project.id, title="Terminado", status="completado", order=1)
    db_session.add_all([pending, done])
    db_session.commit()

    new_period = _create_joint_period(
        client, db_session, [member.id],
        name="Conjunto Q2", start="2026-04-01", end="2026-06-30", carry_over="1",
    )

    titles = {t.title: t for p in new_period.projects for t in p.tickets}
    assert "Pendiente conjunto" in titles
    assert "Terminado" not in titles
    assert [a.email for a in titles["Pendiente conjunto"].assignees] == ["member@example.com"]


def test_joint_carry_over_does_not_pull_from_personal_periods(client, db_session):
    register_first_admin(client)
    temp_password = _invite_member(client)

    from app.models import Period, Ticket, User

    member = db_session.query(User).filter(User.email == "member@example.com").first()

    # Periodo personal previo con un ticket pendiente.
    token = _extract_csrf(client.get("/dashboard").text)
    client.post(
        "/periods",
        data={"name": "Personal previo", "start_date": "2026-01-01", "end_date": "2026-03-31", "csrf_token": token},
    )
    personal = db_session.query(Period).filter(Period.name == "Personal previo").first()
    project = _create_project_in_period(client, db_session, personal, title="Proyecto personal")
    db_session.add(Ticket(project_id=project.id, title="Pendiente personal", status="pendiente", order=0))
    db_session.commit()

    new_joint = _create_joint_period(
        client, db_session, [member.id],
        name="Conjunto Q2", start="2026-04-01", end="2026-06-30", carry_over="1",
    )
    # No hay periodo conjunto anterior -> arranca vacio, sin arrastrar del personal.
    assert new_joint.projects == []


def test_export_snapshot_conjuntos_writes_one_row_per_assignee(client, db_session, tmp_path):
    member, _, period = _setup_admin_member_and_joint_period(client, db_session)
    project = _create_project_in_period(client, db_session, period)

    from app.models import Ticket, User

    admin = db_session.query(User).filter(User.email == "admin@example.com").first()
    shared = Ticket(project_id=project.id, title="Compartido", status="completado", order=0)
    shared.assignees = [admin, member]
    db_session.add(shared)
    db_session.commit()

    import csv

    from scripts.export_report import export_snapshot, export_snapshot_conjuntos

    joint_path = tmp_path / "historial_periodos_conjuntos.csv"
    export_snapshot_conjuntos(db_session, str(joint_path), "2026-07-09T10:00:00")
    with open(joint_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2  # un ticket con 2 responsables -> 2 filas
    assert sorted(r["responsable_email"] for r in rows) == ["admin@example.com", "member@example.com"]
    assert all(r["progreso_grupal_periodo_pct"] == "100.0" for r in rows)
    assert all(r["progreso_individual_responsable_pct"] == "100.0" for r in rows)

    # Append: una segunda corrida agrega filas, no sobrescribe.
    export_snapshot_conjuntos(db_session, str(joint_path), "2026-07-16T10:00:00")
    with open(joint_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4
    assert {r["fecha_extraccion"] for r in rows} == {"2026-07-09T10:00:00", "2026-07-16T10:00:00"}

    # Los periodos conjuntos no aparecen en historial_tickets.csv.
    personal_path = tmp_path / "historial_tickets.csv"
    export_snapshot(db_session, str(personal_path), "2026-07-09T10:00:00")
    with open(personal_path, encoding="utf-8") as f:
        personal_rows = list(csv.DictReader(f))
    assert personal_rows == []
