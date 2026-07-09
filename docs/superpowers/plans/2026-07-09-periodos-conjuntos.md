# Plan de implementacion: Periodos conjuntos

Referencia de diseno: `docs/superpowers/specs/2026-07-09-periodos-conjuntos-design.md`

## Tareas

1. **Modelo de datos**: agregar `Period.is_joint` (Boolean, default False), tablas puente `period_participants` y `ticket_assignees` en `app/models.py` con sus `relationship()`. Migracion Alembic `0004_periodos_conjuntos.py` (stacked sobre `0003_reminder_day`), verificada con `alembic upgrade head` sobre un sqlite descartable.

2. **app/progress.py**: agregar `calculate_individual_progress(period, user) -> float`. Sin cambios a las funciones existentes. Tests unitarios puros (multi-responsable cuenta completo para cada uno, 0 tickets asignados -> 0.0).

3. **Autorizacion compartida**: helper `user_can_access_period(period, user) -> bool` (owner o participante) reutilizable desde `periods.py`, `projects.py`, `tickets.py`. Tests de acceso (participante ve, no-participante recibe 403/404).

4. **POST /periods**: agregar `is_joint` + `participant_ids` al form; crear filas en `period_participants` incluyendo siempre al creador. Extender formulario en `dashboard.html` (selector de tipo + multi-select de usuarios existentes). Tests: crea periodo conjunto con participantes correctos; periodo personal sin cambios de comportamiento.

5. **GET /dashboard**: separar "Mis periodos" vs "Periodos conjuntos" (dos queries, dos secciones en template). Cada periodo conjunto muestra Progreso Grupal (`calculate_period_progress`) y el Progreso individual del usuario actual (`calculate_individual_progress`). Tests de contenido de ambas secciones.

6. **POST /projects**: extender chequeo de autorizacion de "owner_id == current_user.id" a `user_can_access_period`. Tests: participante no-owner puede crear proyecto en periodo conjunto; usuario ajeno no puede.

7. **POST /tickets**: si el proyecto pertenece a un periodo conjunto, exigir `assignee_ids` (>=1, validados contra `period.participants`); si no es conjunto, sin cambios. Guardar en `ticket_assignees`. Tests: creacion sin responsable falla (400) en periodo conjunto; creacion con 2 responsables ok; periodo personal sin exigencia.

8. **Vista de detalle de periodo conjunto** (`GET /periods/{period_id}`, template `joint_period_detail.html`): lista proyectos/tickets con badges de responsables, tabla de progreso individual por participante (grupal arriba). Reusa `kanban_board.html`/`ticket_list.html` con badge de responsables agregado. Tests de render y de que un no-participante recibe 403.

9. **Edicion/estado de ticket en periodo conjunto**: extender autorizacion de los endpoints existentes de cambio de estado/edicion para aceptar a cualquier participante del periodo (no solo el owner). Tests de que un participante no-owner puede cambiar estado.

10. **Carry-over para periodos conjuntos**: extender `_carry_over_pending`/`create_period` en `periods.py` para que, cuando `is_joint=True`, la busqueda de "periodo anterior" se limite al ultimo periodo conjunto del mismo creador (`is_joint=True`, `owner_id==current_user.id`), y que al duplicar tickets pendientes se copien tambien sus `assignees`. Tests: carry-over conjunto preserva responsables; no se mezcla con periodos personales del mismo usuario.

11. **scripts/export_report.py**: agregar `export_snapshot_conjuntos(db, path, stamp)` que escribe (modo append, header solo si el archivo es nuevo) `historial_periodos_conjuntos.csv` con una fila por combinacion (ticket, responsable) de periodos `is_joint=True`, incluyendo `progreso_individual_responsable_pct` y `progreso_grupal_periodo_pct` (snapshot del momento, via `calculate_individual_progress`/`calculate_period_progress`). `main()` llama a ambas funciones de snapshot con el mismo `stamp`. Test: un ticket con 2 responsables genera 2 filas; periodos personales no aparecen en este archivo.

12. **Suite completa + regresion**: correr toda la suite de tests (no solo los nuevos), confirmar que las rutas/tests existentes de periodos personales, proyectos y tickets siguen intactos sin modificar su comportamiento por defecto.

13. **Commit + sync**: commit en el monorepo, copiar cambios al clone de `sebafloamp/Ticketera` y push, siguiendo el patron ya usado en la sesion.

## Fuera de alcance (ver spec)
- Panel de admin, reminders -- no se tocan en esta iteracion.
