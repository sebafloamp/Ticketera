# Propuesta de reporte Power BI — Ticketera Individual

Basado en `scripts/export_report.py`, que genera dos CSV **acumulativos** (cada corrida agrega filas nuevas, no sobrescribe):

- `historial_tickets.csv` — tickets de periodos **individuales**.
- `historial_periodos_conjuntos.csv` — combinaciones (ticket, responsable) de periodos **conjuntos**.

Cada fila lleva `fecha_extraccion`: el instante exacto en que corriste el script. **Todas las filas de una misma corrida comparten el mismo valor** (es un timestamp único por ejecución, no por fila), lo que hace posible aislar "la foto más reciente" con una medida DAX en vez de tener que filtrar a mano.

> Para que la parte de tendencia en el tiempo (Página 3) tenga sentido, `python scripts/export_report.py` debe correr periódicamente (ideal: 1 vez por semana, ej. vía una tarea programada). Con una sola corrida solo vas a tener una foto, sin evolución que graficar.

---

## 1. Preparación en Power BI

1. **Obtener datos → Texto/CSV** para cada archivo. Ubicación sugerida: donde vivan los CSV (hoy en la raíz de `pythonProject/`, pero podrías apuntar el script a una carpeta fija dentro de `Ticketera Individual/reportes/` y usar esa ruta).
2. Tipos de columna a fijar en Power Query (el importador a veces no acierta):
   - `fecha_extraccion`, `fecha_limite`, `ticket_creado`, `ticket_actualizado` → **Fecha/hora**.
   - `proyecto_progreso_pct`, `progreso_individual_responsable_pct`, `progreso_grupal_periodo_pct` → **Decimal** (vienen 0–100, no 0–1).
   - `proyecto_id`, `ticket_id`, `periodo_id` → **Número entero** (evita que Power BI los sume por accidente en visuales; igual conviene marcarlos "No resumir" en el panel de campos).
3. Nombra las tablas `Tickets_Individual` y `Tickets_Conjunto` para que coincidan con las medidas de abajo (o ajusta los nombres en el DAX si prefieres otros).
4. **No hace falta relacionar las dos tablas entre sí** — son dos universos distintos (individual vs. conjunto). Si quieres, crea una tabla de fechas (`Calendario`) con `CALENDAR()` y relaciónala con `fecha_limite` de ambas tablas para usar Time Intelligence nativo en la Página 2.

---

## 2. Medidas — `Tickets_Individual`

### Base: aislar la última foto

```dax
Última Extracción =
MAX ( Tickets_Individual[fecha_extraccion] )
```

```dax
Tickets (Vigentes) =
CALCULATE (
    DISTINCTCOUNT ( Tickets_Individual[ticket_id] ),
    FILTER (
        ALL ( Tickets_Individual[fecha_extraccion] ),
        Tickets_Individual[fecha_extraccion] = [Última Extracción]
    )
)
```

`[Tickets (Vigentes)]` es la base de casi todo lo demás: cuenta tickets únicos solo en la corrida más reciente, ignorando las fotos históricas, pero respetando cualquier otro filtro/slicer (proyecto, periodo, prioridad, etc.).

### Estado

```dax
Tickets Pendientes =
CALCULATE ( [Tickets (Vigentes)], Tickets_Individual[estado] = "pendiente" )

Tickets En Progreso =
CALCULATE ( [Tickets (Vigentes)], Tickets_Individual[estado] = "en_progreso" )

Tickets Completados =
CALCULATE ( [Tickets (Vigentes)], Tickets_Individual[estado] = "completado" )

% Completados =
DIVIDE ( [Tickets Completados], [Tickets (Vigentes)] )
```

### Cumplimiento de plazos

```dax
Tickets Vencidos =
CALCULATE (
    [Tickets (Vigentes)],
    Tickets_Individual[estado] <> "completado",
    Tickets_Individual[fecha_limite] < TODAY ()
)

Tickets Por Vencer (7 días) =
CALCULATE (
    [Tickets (Vigentes)],
    Tickets_Individual[estado] <> "completado",
    Tickets_Individual[fecha_limite] >= TODAY (),
    Tickets_Individual[fecha_limite] <= TODAY () + 7
)

Sin Fecha de Término =
CALCULATE (
    [Tickets (Vigentes)],
    ISBLANK ( Tickets_Individual[fecha_limite] )
)
```

### Progreso de proyectos

`proyecto_progreso_pct` viene **repetido** en cada fila de ticket del mismo proyecto (no es un valor por ticket). Promediarlo con `AVERAGE` directo sobrepondera a los proyectos con más tickets — hay que des-duplicar antes:

```dax
Progreso Promedio Proyectos =
VAR UltimaFecha = [Última Extracción]
VAR ProyectosUnicos =
    FILTER (
        SUMMARIZE (
            Tickets_Individual,
            Tickets_Individual[proyecto_id],
            Tickets_Individual[proyecto_progreso_pct],
            Tickets_Individual[fecha_extraccion]
        ),
        Tickets_Individual[fecha_extraccion] = UltimaFecha
    )
RETURN
    AVERAGEX ( ProyectosUnicos, Tickets_Individual[proyecto_progreso_pct] )
```

### Ciclo de vida (aproximado)

El modelo no guarda una fecha de "completado" explícita — solo `ticket_actualizado` (última edición). Como proxy razonable, para tickets ya completados:

```dax
Días Creado→Actualizado (Completados) =
AVERAGEX (
    FILTER (
        Tickets_Individual,
        Tickets_Individual[estado] = "completado"
            && Tickets_Individual[fecha_extraccion] = [Última Extracción]
    ),
    DATEDIFF ( Tickets_Individual[ticket_creado], Tickets_Individual[ticket_actualizado], DAY )
)
```

⚠️ Ojo: si un ticket completado se vuelve a editar después (ej. cambia su descripción), `ticket_actualizado` se corre y esta medida deja de reflejar el momento real de cierre. Sirve como estimación, no como dato exacto — si te importa la precisión, lo correcto sería agregar un campo `completed_at` al modelo de `Ticket` en la app (lo dejo anotado, no lo hice porque no lo pediste).

```dax
Atraso Promedio (Completados, días) =
AVERAGEX (
    FILTER (
        Tickets_Individual,
        Tickets_Individual[estado] = "completado"
            && Tickets_Individual[fecha_extraccion] = [Última Extracción]
            && NOT ISBLANK ( Tickets_Individual[fecha_limite] )
            && Tickets_Individual[ticket_actualizado] > Tickets_Individual[fecha_limite]
    ),
    DATEDIFF ( Tickets_Individual[fecha_limite], Tickets_Individual[ticket_actualizado], DAY )
)
```

### Tendencia (usa TODAS las fotos, no solo la última)

Estas se comportan bien puestas contra `fecha_extraccion` en un eje de gráfico de líneas — no necesitan el truco de "última foto":

```dax
Tickets en Snapshot = DISTINCTCOUNT ( Tickets_Individual[ticket_id] )

Completados en Snapshot =
CALCULATE ( [Tickets en Snapshot], Tickets_Individual[estado] = "completado" )
```

Para el gráfico de "tickets creados por semana" no hace falta una medida nueva: usa `[Tickets en Snapshot]` de nuevo, pero con `ticket_creado` (agrupado por semana) en el eje del visual en vez de `fecha_extraccion`. Como la medida ya usa `DISTINCTCOUNT`, un mismo ticket que aparece repetido en 5 fotos distintas solo cuenta una vez dentro de la semana en que fue creado.

---

## 3. Medidas — `Tickets_Conjunto`

Esta tabla tiene **una fila por combinación (ticket, responsable)** — un ticket con 3 responsables aparece 3 veces. Igual que arriba, contar tickets requiere `DISTINCTCOUNT`, no `COUNTROWS`.

```dax
Última Extracción (Conjuntos) =
MAX ( Tickets_Conjunto[fecha_extraccion] )

Tickets Conjuntos (Vigentes) =
CALCULATE (
    DISTINCTCOUNT ( Tickets_Conjunto[ticket_id] ),
    FILTER (
        ALL ( Tickets_Conjunto[fecha_extraccion] ),
        Tickets_Conjunto[fecha_extraccion] = [Última Extracción (Conjuntos)]
    )
)

Responsables Activos =
CALCULATE (
    DISTINCTCOUNT ( Tickets_Conjunto[responsable_email] ),
    FILTER (
        ALL ( Tickets_Conjunto[fecha_extraccion] ),
        Tickets_Conjunto[fecha_extraccion] = [Última Extracción (Conjuntos)]
    )
)
```

`progreso_individual_responsable_pct` y `progreso_grupal_periodo_pct` también vienen repetidos (por fila de ticket, no por responsable/periodo) — mismo des-duplicado que en `proyecto_progreso_pct`:

```dax
Progreso Individual Promedio =
VAR UltimaFecha = [Última Extracción (Conjuntos)]
VAR ResponsablesUnicos =
    FILTER (
        SUMMARIZE (
            Tickets_Conjunto,
            Tickets_Conjunto[responsable_email],
            Tickets_Conjunto[periodo_id],
            Tickets_Conjunto[progreso_individual_responsable_pct],
            Tickets_Conjunto[fecha_extraccion]
        ),
        Tickets_Conjunto[fecha_extraccion] = UltimaFecha
    )
RETURN
    AVERAGEX ( ResponsablesUnicos, Tickets_Conjunto[progreso_individual_responsable_pct] )

Progreso Grupal Promedio =
VAR UltimaFecha = [Última Extracción (Conjuntos)]
VAR PeriodosUnicos =
    FILTER (
        SUMMARIZE (
            Tickets_Conjunto,
            Tickets_Conjunto[periodo_id],
            Tickets_Conjunto[progreso_grupal_periodo_pct],
            Tickets_Conjunto[fecha_extraccion]
        ),
        Tickets_Conjunto[fecha_extraccion] = UltimaFecha
    )
RETURN
    AVERAGEX ( PeriodosUnicos, Tickets_Conjunto[progreso_grupal_periodo_pct] )
```

---

## 4. Páginas de reporte sugeridas

### Página 1 — Resumen general
- **Tarjetas (KPI)**: `Tickets (Vigentes)`, `% Completados`, `Tickets Vencidos`, `Progreso Promedio Proyectos`.
- **Gráfico de barras apiladas**: tickets por `proyecto` × `estado`.
- **Gráfico de anillo**: tickets por `prioridad`.
- **Tabla**: `proyecto`, `Tickets (Vigentes)`, `Progreso Promedio Proyectos`, `Tickets Vencidos`.
- **Slicers**: `periodo`, `usuario_nombre`, rango de `fecha_limite`.

### Página 2 — Cumplimiento de plazos
- **Tarjetas**: `Tickets Vencidos`, `Tickets Por Vencer (7 días)`, `Atraso Promedio (Completados, días)`.
- **Tabla detalle**: tickets vencidos (`ticket`, `proyecto`, `prioridad`, `fecha_limite`, días de atraso calculado), ordenada por más atrasado primero.
- **Gráfico de barras**: vencidos por `prioridad`.

### Página 3 — Evolución en el tiempo
- **Gráfico de líneas**: `Tickets en Snapshot` y `Completados en Snapshot` por `fecha_extraccion` (una línea por estado, o un área apilada).
- **Gráfico de columnas**: `Tickets Creados (por semana)` usando `ticket_creado`.
- Útil para ver si el equipo/tú van más rápido creando tickets que cerrándolos.

### Página 4 — Periodos conjuntos (responsables)
- **Tarjetas**: `Tickets Conjuntos (Vigentes)`, `Responsables Activos`, `Progreso Grupal Promedio`.
- **Gráfico de barras**: `Progreso Individual Promedio` por `responsable_nombre`, con línea de referencia en `Progreso Grupal Promedio` (gráfico combinado).
- **Tabla**: `responsable_nombre`, tickets asignados (`DISTINCTCOUNT` de `ticket_id` filtrado por responsable), tickets completados, % completados por persona.

---

## 5. Notas y limitaciones

- **Fan-out en `Tickets_Conjunto`**: cualquier medida nueva que agregues ahí debe pasar por `ticket_id` con `DISTINCTCOUNT`, nunca `COUNTROWS`, o vas a contar el mismo ticket varias veces.
- **Columnas "repetidas por fila"** (`proyecto_progreso_pct`, `progreso_individual_responsable_pct`, `progreso_grupal_periodo_pct`): no promediarlas directo con `AVERAGE`; usa el patrón `SUMMARIZE` + `AVERAGEX` de arriba.
- **La fecha de cierre real no existe** — todo lo que use "completado" como proxy de fecha de término (`Días Creado→Actualizado`, `Atraso Promedio`) es una aproximación razonable, no exacta.
- **El reporte solo tiene tendencia real si el script corre seguido.** Con una corrida aislada, la Página 3 va a mostrar un solo punto.
- Todo el DAX de arriba asume que renombraste las tablas `Tickets_Individual` / `Tickets_Conjunto`. Si prefieres mantener los nombres de archivo (`historial_tickets` / `historial_periodos_conjuntos`), solo reemplaza el nombre de tabla en cada medida.
