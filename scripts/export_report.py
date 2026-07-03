"""Exporta dos reportes CSV de la base de datos: tickets detallados y progreso por proyecto.

Uso:
    DATABASE_URL=postgresql://... python scripts/export_report.py [directorio_salida]

Si no se pasa DATABASE_URL, usa la misma variable de entorno que la app (.env / entorno actual).
"""
import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal  # noqa: E402
from app.models import Period, Project, Ticket, User  # noqa: E402
from app.progress import calculate_project_progress  # noqa: E402


def export_tickets(db, path):
    rows = (
        db.query(Ticket, Project, Period, User)
        .join(Project, Ticket.project_id == Project.id)
        .join(Period, Project.period_id == Period.id)
        .join(User, Period.owner_id == User.id)
        .order_by(User.email, Period.name, Project.title, Ticket.order)
        .all()
    )
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "usuario_email", "usuario_nombre", "periodo", "proyecto", "ticket",
            "descripcion", "estado", "prioridad", "fecha_limite", "creado", "actualizado",
        ])
        for ticket, project, period, user in rows:
            writer.writerow([
                user.email, user.name, period.name, project.title, ticket.title,
                ticket.description, ticket.status, ticket.priority,
                ticket.due_date.isoformat() if ticket.due_date else "",
                ticket.created_at.isoformat() if ticket.created_at else "",
                ticket.updated_at.isoformat() if ticket.updated_at else "",
            ])
    print(f"Escrito {path} ({len(rows)} tickets)")


def export_project_progress(db, path):
    rows = (
        db.query(Project, Period, User)
        .join(Period, Project.period_id == Period.id)
        .join(User, Period.owner_id == User.id)
        .order_by(User.email, Period.name, Project.title)
        .all()
    )
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "usuario_email", "usuario_nombre", "periodo", "proyecto",
            "progreso_pct", "total_tickets", "pendientes", "en_progreso", "completados",
        ])
        for project, period, user in rows:
            tickets = project.tickets
            pendientes = sum(1 for t in tickets if t.status == "pendiente")
            en_progreso = sum(1 for t in tickets if t.status == "en_progreso")
            completados = sum(1 for t in tickets if t.status == "completado")
            writer.writerow([
                user.email, user.name, period.name, project.title,
                calculate_project_progress(project), len(tickets),
                pendientes, en_progreso, completados,
            ])
    print(f"Escrito {path} ({len(rows)} proyectos)")


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    db = SessionLocal()
    try:
        export_tickets(db, os.path.join(out_dir, f"tickets_{stamp}.csv"))
        export_project_progress(db, os.path.join(out_dir, f"progreso_proyectos_{stamp}.csv"))
    finally:
        db.close()


if __name__ == "__main__":
    main()
