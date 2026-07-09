from app.models import Period, Project, User


def calculate_project_progress(project: Project) -> float:
    tickets = project.tickets
    if not tickets:
        return 0.0
    done = sum(1 for ticket in tickets if ticket.status == "completado")
    return round((done / len(tickets)) * 100, 1)


def calculate_period_progress(period: Period) -> float:
    projects = period.projects
    if not projects:
        return 0.0
    total = sum(calculate_project_progress(project) for project in projects)
    return round(total / len(projects), 1)


def calculate_individual_progress(period: Period, user: User) -> float:
    """% de tickets del periodo asignados a `user` que estan completados.

    Un ticket con varios responsables cuenta completo para cada uno (no se divide).
    Sin tickets asignados en el periodo -> 0.0.
    """
    assigned = [
        ticket
        for project in period.projects
        for ticket in project.tickets
        if any(assignee.id == user.id for assignee in ticket.assignees)
    ]
    if not assigned:
        return 0.0
    done = sum(1 for ticket in assigned if ticket.status == "completado")
    return round((done / len(assigned)) * 100, 1)


def calculate_user_progress(periods: list[Period]) -> float:
    """Promedio del avance de todos los periodos del usuario (historicos incluidos)."""
    if not periods:
        return 0.0
    total = sum(calculate_period_progress(period) for period in periods)
    return round(total / len(periods), 1)
