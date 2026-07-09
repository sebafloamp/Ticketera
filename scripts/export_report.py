"""Exporta un CSV unico con el detalle de tickets y el progreso de su proyecto.

Cada ejecucion AGREGA filas nuevas (no sobrescribe), con una columna
`fecha_extraccion` que marca el snapshot. Pensado para alimentar un reporte
de Power BI que registre la evolucion de estados en el tiempo: cada corrida
del script queda como una fotografia mas en el historial.

Uso:
    DATABASE_URL=postgresql://... python scripts/export_report.py [directorio_salida]

Si no se pasa DATABASE_URL, usa la misma variable de entorno que la app (.env / entorno actual).
"""
import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _load_env_file():
    """Carga variables desde .env si existen y no están ya definidas en el entorno."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_env_file()

from app.database import SessionLocal  # noqa: E402
from app.models import Period, Project, Ticket, User  # noqa: E402
from app.progress import (  # noqa: E402
    calculate_individual_progress,
    calculate_period_progress,
    calculate_project_progress,
)


FIELDNAMES = [
    "fecha_extraccion",
    "usuario_email", "usuario_nombre",
    "periodo",
    "proyecto_id", "proyecto", "proyecto_progreso_pct",
    "ticket_id", "ticket", "estado", "prioridad",
    "fecha_limite", "ticket_creado", "ticket_actualizado",
]

JOINT_FIELDNAMES = [
    "fecha_extraccion",
    "periodo_id", "periodo",
    "proyecto_id", "proyecto",
    "ticket_id", "ticket", "estado", "prioridad",
    "responsable_email", "responsable_nombre",
    "progreso_individual_responsable_pct",
    "progreso_grupal_periodo_pct",
    "fecha_limite", "ticket_creado", "ticket_actualizado",
]


def export_snapshot(db, path, stamp):
    rows = (
        db.query(Ticket, Project, Period, User)
        .join(Project, Ticket.project_id == Project.id)
        .join(Period, Project.period_id == Period.id)
        .join(User, Period.owner_id == User.id)
        .filter(Period.is_joint.is_(False))
        .order_by(User.email, Period.name, Project.title, Ticket.order)
        .all()
    )

    progress_by_project = {}
    for _, project, _, _ in rows:
        if project.id not in progress_by_project:
            progress_by_project[project.id] = calculate_project_progress(project)

    file_is_new = not os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if file_is_new:
            writer.writeheader()
        for ticket, project, period, user in rows:
            writer.writerow({
                "fecha_extraccion": stamp,
                "usuario_email": user.email,
                "usuario_nombre": user.name,
                "periodo": period.name,
                "proyecto_id": project.id,
                "proyecto": project.title,
                "proyecto_progreso_pct": progress_by_project[project.id],
                "ticket_id": ticket.id,
                "ticket": ticket.title,
                "estado": ticket.status,
                "prioridad": ticket.priority,
                "fecha_limite": ticket.due_date.isoformat() if ticket.due_date else "",
                "ticket_creado": ticket.created_at.isoformat() if ticket.created_at else "",
                "ticket_actualizado": ticket.updated_at.isoformat() if ticket.updated_at else "",
            })
    print(f"Agregadas {len(rows)} filas a {path} (snapshot {stamp})")


def export_snapshot_conjuntos(db, path, stamp):
    """Snapshot de periodos conjuntos: una fila por combinacion (ticket, responsable)."""
    joint_periods = db.query(Period).filter(Period.is_joint.is_(True)).order_by(Period.name).all()

    row_count = 0
    file_is_new = not os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=JOINT_FIELDNAMES)
        if file_is_new:
            writer.writeheader()
        for period in joint_periods:
            group_pct = calculate_period_progress(period)
            individual_pct = {
                participant.id: calculate_individual_progress(period, participant)
                for participant in period.participants
            }
            for project in sorted(period.projects, key=lambda p: p.title):
                for ticket in sorted(project.tickets, key=lambda t: t.order):
                    for assignee in sorted(ticket.assignees, key=lambda u: u.email):
                        writer.writerow({
                            "fecha_extraccion": stamp,
                            "periodo_id": period.id,
                            "periodo": period.name,
                            "proyecto_id": project.id,
                            "proyecto": project.title,
                            "ticket_id": ticket.id,
                            "ticket": ticket.title,
                            "estado": ticket.status,
                            "prioridad": ticket.priority,
                            "responsable_email": assignee.email,
                            "responsable_nombre": assignee.name,
                            "progreso_individual_responsable_pct": individual_pct.get(assignee.id, 0.0),
                            "progreso_grupal_periodo_pct": group_pct,
                            "fecha_limite": ticket.due_date.isoformat() if ticket.due_date else "",
                            "ticket_creado": ticket.created_at.isoformat() if ticket.created_at else "",
                            "ticket_actualizado": ticket.updated_at.isoformat() if ticket.updated_at else "",
                        })
                        row_count += 1
    print(f"Agregadas {row_count} filas a {path} (snapshot {stamp})")


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().isoformat(timespec="seconds")

    path = os.path.join(out_dir, "historial_tickets.csv")
    joint_path = os.path.join(out_dir, "historial_periodos_conjuntos.csv")

    db = SessionLocal()
    try:
        export_snapshot(db, path, stamp)
        export_snapshot_conjuntos(db, joint_path, stamp)
    finally:
        db.close()


if __name__ == "__main__":
    main()
