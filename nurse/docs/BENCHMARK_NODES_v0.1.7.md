# Nurse benchmark v0.1.7: métricas UCI y alineación

- El nombre del player UCI que se muestra en el encabezado proviene de `engine_name` en el brain si se declara; de lo contrario proviene de `Path(cfg["_engine"]).stem`. **No** representa necesariamente el `id name` reportado por el motor UCI.
- El campo `nodes` es el número emitido literalmente en `info nodes N`. No se calcula a partir de `simulations`.
- En AlphaZero C++ el campo `nodes` es el número de nodos del árbol MCTS (`r.nodes`); las simulaciones (`r.simulations`) se emiten por separado. En Stockfish `nodes` corresponde al trabajo de búsqueda alfa-beta. No comparar directamente los NPS de dos algoritmos heterogéneos como criterio de fuerza.
- `--simulations 1200` puede detener AlphaZero antes del límite `tmax`, sin constituir un problema de rendimiento.
- `nodes=` se representa en una columna de anchura mínima 12, alineada a derecha; no se alteran `moves.csv`, el cálculo del campo ni la telemetría adicional.
