# Diseno: Periodos conjuntos

## Resumen
Un "Periodo conjunto" es un periodo con varios participantes (en vez de un unico owner). Dentro de sus proyectos, cada ticket requiere uno o mas responsables (asignados de la lista de participantes). Se muestra "Progreso Grupal" (igual al progreso de periodo actual) y "Progreso individual" por participante (basado solo en los tickets que tiene asignados dentro de ese periodo).

## Decisiones (brainstorming)
1. **Creacion**: cualquier usuario puede crear un periodo conjunto. Al crearlo, selecciona participantes existentes (multi-select). El creador queda incluido automaticamente como participante.
2. **Tipo fijo**: se elige "personal" o "conjunto" al crear el periodo; no es convertible despues.
3. **Responsables de ticket**: obligatorio elegir al menos un responsable al crear el ticket; se permiten multiples responsables por ticket.
4. **Progreso individual**: se calcula solo dentro del periodo conjunto (tickets asignados a ese usuario / completados). No se mezcla con el "historial de progreso" personal de `/profile` (que sigue promediando solo periodos personales).
5. **Progreso multi-responsable**: si un ticket con varios responsables se completa, cuenta como 1 ticket completado para el % individual de CADA responsable (no se divide).
6. **Permisos dentro del periodo**: cualquier participante puede crear proyectos, crear tickets, asignar/reasignar responsables y cambiar el estado de cualquier ticket del periodo (colaborativo, sin jerarquia interna).
7. **UI**: el dashboard muestra dos secciones: "Mis periodos" (personales, como hoy) y "Periodos conjuntos" (donde el usuario participa).
8. **Carry-over**: mismo comportamiento que periodos personales -- al crear un nuevo periodo conjunto con fecha posterior, se arrastran tickets pendientes/en_progreso del periodo conjunto anterior (mismo creador), conservando sus responsables. Solo se compara contra el periodo conjunto anterior mas reciente del mismo creador (no se mezcla con el historial de periodos personales).

## Modelo de datos
```
Period.is_joint: bool (default False)      # nueva columna
Period.owner_id sigue existiendo = creador

period_participants (tabla puente)
  period_id -> periods.id
  user_id   -> users.id
  (PK compuesta; incluye siempre al creador)

ticket_assignees (tabla puente)
  ticket_id -> tickets.id
  user_id   -> users.id
  (PK compuesta; 1..N responsables por ticket)
```
Migracion Alembic nueva (`0004_periodos_conjuntos.py`) stacked sobre `0003_reminder_day`.

## Reglas de autorizacion (cambios)
- Acceso a un periodo: `is_joint=False` -> solo `owner_id == current_user.id` (igual que hoy). `is_joint=True` -> `current_user.id in period.participants`.
- Crear proyecto dentro de un periodo: mismo chequeo de acceso al periodo (dueno o participante).
- Crear/editar ticket: mismo chequeo, via el proyecto -> periodo.
- El asignar responsables solo permite elegir usuarios que sean participantes de ese periodo especifico.

## Calculo de progreso (app/progress.py)
- `calculate_project_progress` y `calculate_period_progress`: SIN CAMBIOS, se reusan tal cual (esto es el "Progreso Grupal").
- Nueva funcion `calculate_individual_progress(period, user) -> float`: sobre todos los tickets de todos los proyectos del periodo donde `user` figura en `assignees`, `% = completados / asignados`. Si no tiene tickets asignados en el periodo, devuelve `0.0`.
- `calculate_user_progress` (historial de `/profile`) SIN CAMBIOS: sigue promediando solo periodos con `owner_id == user.id` y `is_joint == False`. Los periodos conjuntos no entran en el historial personal (decision 4).

## Rutas nuevas/afectadas
- `POST /periods`: agrega campos `is_joint` (checkbox) y `participant_ids` (multi-select de usuarios existentes, excluyendo al propio usuario que ya queda incluido). Si `is_joint`, crea las filas en `period_participants`.
- `GET /dashboard`: separa la query en periodos personales (como hoy) y periodos conjuntos (`join period_participants` donde `user_id = current_user.id` y `is_joint=True`), cada seccion con su propio render. Los periodos conjuntos muestran Progreso Grupal + el Progreso individual del usuario actual como badge.
- `GET /periods/{period_id}` (nueva vista de detalle, reusa patron de `project_detail`): lista proyectos/tickets del periodo conjunto, con badge de responsables por ticket y tabla de progreso individual por participante.
- `POST /projects`: chequeo de autorizacion extendido de "es el owner" a "es owner o participante".
- `POST /tickets`: si el proyecto pertenece a un periodo conjunto, el form incluye un multi-select `assignee_ids` (obligatorio, de la lista de participantes); si no, comportamiento actual sin cambios.
- Ticket status update / edit: mismo chequeo de autorizacion extendido.

## Extractor CSV (scripts/export_report.py)
Los periodos conjuntos NO entran en `historial_tickets.csv` (ese archivo asume un solo owner por ticket via `Period.owner_id`, y un ticket conjunto puede tener varios responsables). Se agrega un segundo snapshot append-only, mismo patron (mismo `stamp`, mismo modo `"a"`, header solo si el archivo es nuevo):

**Archivo nuevo**: `historial_periodos_conjuntos.csv`, una fila por combinacion (ticket, responsable) de tickets que pertenecen a periodos con `is_joint=True`.

Columnas:
```
fecha_extraccion,
periodo_id, periodo,
proyecto_id, proyecto,
ticket_id, ticket, estado, prioridad,
responsable_email, responsable_nombre,
progreso_individual_responsable_pct,   # calculate_individual_progress(period, responsable), snapshot del momento
progreso_grupal_periodo_pct,           # calculate_period_progress(period), snapshot del momento
fecha_limite, ticket_creado, ticket_actualizado
```
Un ticket con 2 responsables genera 2 filas (una por responsable), cada una con su propio `progreso_individual_responsable_pct` pero el mismo `progreso_grupal_periodo_pct`. Esto permite en Power BI filtrar/agrupar tanto por persona como por periodo conjunto completo.

`main()` llama a ambas funciones de snapshot (`export_snapshot` para personales, `export_snapshot_conjuntos` para conjuntos) con el mismo `stamp`, escribiendo dos archivos separados en el mismo `out_dir`.

## Fuera de alcance (explicito)
- El panel de admin (`/admin`) no se modifica en esta iteracion; queda como trabajo futuro si se pide.
- No hay notificaciones/reminders especificos para periodos conjuntos en esta iteracion (los reminders existentes siguen basados en periodos personales).
