from datetime import datetime

from app.models import Period, Project, Ticket, User


def _make_project(db_session):
    user = User(email="a@a.com", name="A", password_hash="x")
    db_session.add(user)
    db_session.flush()
    period = Period(owner_id=user.id, name="Q1", start_date=datetime(2026, 1, 1), end_date=datetime(2026, 3, 31))
    db_session.add(period)
    db_session.flush()
    project = Project(period_id=period.id, title="Cliente X")
    db_session.add(project)
    db_session.flush()
    return project


def test_project_progress_is_zero_with_no_tickets(db_session):
    from app.progress import calculate_project_progress

    project = _make_project(db_session)
    assert calculate_project_progress(project) == 0.0


def test_project_progress_is_100_when_all_tickets_completed(db_session):
    from app.progress import calculate_project_progress

    project = _make_project(db_session)
    db_session.add_all(
        [
            Ticket(project_id=project.id, title="t1", status="completado", order=0),
            Ticket(project_id=project.id, title="t2", status="completado", order=1),
        ]
    )
    db_session.flush()
    db_session.refresh(project)
    assert calculate_project_progress(project) == 100.0


def test_project_progress_partial_and_no_credit_for_en_progreso(db_session):
    from app.progress import calculate_project_progress

    project = _make_project(db_session)
    db_session.add_all(
        [
            Ticket(project_id=project.id, title="t1", status="completado", order=0),
            Ticket(project_id=project.id, title="t2", status="en_progreso", order=1),
            Ticket(project_id=project.id, title="t3", status="pendiente", order=2),
        ]
    )
    db_session.flush()
    db_session.refresh(project)
    assert calculate_project_progress(project) == round(100 / 3, 1)


def test_period_progress_is_average_of_project_progress(db_session):
    from app.progress import calculate_period_progress

    project1 = _make_project(db_session)
    project2 = Project(period_id=project1.period_id, title="Cliente Y")
    db_session.add(project2)
    db_session.flush()
    db_session.add_all(
        [
            Ticket(project_id=project1.id, title="t1", status="completado", order=0),
            Ticket(project_id=project2.id, title="t1", status="pendiente", order=0),
        ]
    )
    db_session.flush()
    period = project1.period
    db_session.refresh(period)
    assert calculate_period_progress(period) == 50.0


def test_period_progress_is_zero_with_no_projects(db_session):
    from app.progress import calculate_period_progress

    project = _make_project(db_session)
    period = project.period
    db_session.delete(project)
    db_session.flush()
    db_session.refresh(period)
    assert calculate_period_progress(period) == 0.0
