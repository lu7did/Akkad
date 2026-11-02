# Cobertura de caché Bellman y misses NNUE

Parche incremental sobre el `sargon_match.py` con `--telemetry` y los parámetros Bellman A/B.

## Ejecutar

```powershell
python -m sargon_nnue.sargon_match --brain ..\etc\brains\brains.json --idA emma --idB belly --pairs 1 --telemetry --bellman-misses-jsonl ..\data\bellman_misses.jsonl
```

El resumen por partida se muestra incluso sin `--telemetry`. `--telemetry` sigue controlando el detalle por movimiento. `--bellman-misses-jsonl` agrega entradas al archivo sin sobrescribirlo. El archivo es JSON Lines, **no un único JSON contenedor**.

- `consultas`: turnos del player Bellman.
- `estados_hit`: turnos con al menos un movimiento legal en caché, antes del filtro Nmin.
- `hits_acciones`: suma de movimientos legales que encontraron una acción almacenada, contando todas las consultas.
- `politicas_elegibles`: turnos con alguna acción cuyo N >= Nmin. Pueden no ser elegibles para la decisión final si sus expectativas son negativas.
- `decisiones_cache`: turnos donde se seleccionó una acción Bellman.
- `fallback_NNUE`: turnos resueltos por el buscador alternativo.
- `N_elegida_total` / `N_elegida_media`: suma/media de observaciones históricas para las acciones elegidas por caché; no son nodos del movimiento actual.

Cada `fallback` contiene identidad de corrida/partida, FEN original, UCI elegido, estado Bellman, profundidad, evaluación en centipeones desde blancas y cobertura de la consulta. También se escribe un evento `game_end` con el resultado. **El resultado de la partida no es una etiqueta WDL de la jugada del buscador**: la destilación futura deberá decidir método de etiquetado/validación y controlar duplicados, posiciones repetidas y colores.

Los eventos son independientes del SQLite de Bellman y no se insertan automáticamente como políticas. El parser usa la última línea `info string bellman` por movimiento, por lo que requiere un motor que emita la telemetría estructurada del parche anterior.

