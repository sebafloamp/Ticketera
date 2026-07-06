from app.progress import calculate_period_progress, calculate_user_progress

WEEKDAY_NAMES = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

PENDING_STATUSES = ("pendiente", "en_progreso")


def _pending_tickets_by_project(periods) -> list[tuple[str, list]]:
    """[(project_title, [ticket, ...]), ...] solo proyectos con algo sin completar."""
    result = []
    for period in periods:
        for project in period.projects:
            pending = [t for t in project.tickets if t.status in PENDING_STATUSES]
            if pending:
                result.append((project.title, pending))
    return result


def build_user_reminder(user, periods) -> tuple[str, str] | None:
    """Devuelve (subject, html) o None si el usuario no tiene nada pendiente."""
    grouped = _pending_tickets_by_project(periods)
    if not grouped:
        return None

    subject = "Ticketera Individual - tus pendientes de la semana"
    rows = ""
    for project_title, tickets in grouped:
        items = "".join(
            f"<li>{ticket.title} ({ticket.status})</li>" for ticket in sorted(tickets, key=lambda t: t.order)
        )
        rows += f"<h3>{project_title}</h3><ul>{items}</ul>"

    html = f"<h2>Hola {user.name},</h2><p>Este es tu resumen semanal de pendientes:</p>{rows}"
    return subject, html


def build_admin_reminder(members_periods: dict) -> tuple[str, str] | None:
    """members_periods: {User: [Period, ...]}. Devuelve (subject, html) o None si nadie tiene periodos."""
    if not members_periods:
        return None

    subject = "Ticketera Individual - resumen semanal del equipo"
    rows = ""
    for member, periods in members_periods.items():
        if not periods:
            continue
        average = calculate_user_progress(periods)
        period_lines = "".join(
            f"<li>{period.name}: {calculate_period_progress(period)}%</li>" for period in periods
        )
        rows += f"<h3>{member.name} ({member.email}) - promedio {average}%</h3><ul>{period_lines}</ul>"

    if not rows:
        return None
    html = f"<h2>Resumen semanal del equipo</h2>{rows}"
    return subject, html
