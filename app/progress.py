from app.models import Period, Project


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
