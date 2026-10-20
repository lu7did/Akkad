# Sargon-NNUE v0.6.22

## TURBO operativo

Partiendo de v0.6.21, `--turbo` deja de ser una interfaz staged y activa los dos actuadores acordados sin modificar el baseline.

- `--turbo 0`: línea de base estricta. `SargonPlusPlayer.choose()` delega en el scheduler canónico de `SargonCore`; TURBO no interviene.
- `--turbo 0x01`: **Adaptive Full Width**. Antes de iniciar un nivel superior, compara el presupuesto restante con el coste full-width proyectado. Si no cabe, no inicia el nivel y conserva el último nivel completo.
- `--turbo 0x02`: **Adaptive Candidate Selection**. Cuando el full-width proyectado no cabe y existe un nivel inferior completo, usa el presupuesto para calcular dinámicamente `K` y profundiza sólo los mejores candidatos del último nivel completo.
- `--turbo 0x03`: combina ambos actuadores: Full Width decide si el nivel completo cabe; si no, Candidate Selection utiliza el presupuesto restante.

## Complexity / Cost Model

No se introduce un branching factor fijo ni un umbral por cantidad de jugadas legales.

- El crecimiento se aprende de los tiempos reales de niveles full-width consecutivos.
- Se conserva una ventana corta de muestras y se utiliza la mediana como estimador robusto.
- Un timeout parcial aporta una observación censurada: `coste_total ~= tiempo_observado / fracción_root_completada`.
- Mientras no exista evidencia empírica suficiente, TURBO permanece neutral e inicia el nivel full-width normal.

## Clock Controller

El presupuesto operativo continúa siendo el `tmax` total de la jugada. D1 sigue siendo obligatorio y no interrumpible. TURBO sólo administra el presupuesto restante después de D1 y no modifica la política del Core.

## Telemetría

Las intervenciones TURBO se anuncian con `⚡`:

- observación de coste y crecimiento;
- estimación censurada de un nivel interrumpido;
- omisión preventiva de full-width;
- cantidad dinámica de candidatos y finalización del nivel selectivo.

Los bits reservados 2..7 continúan sin algoritmo asignado.
