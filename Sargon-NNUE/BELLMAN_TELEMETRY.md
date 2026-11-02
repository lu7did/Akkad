# Telemetría BellmanR (parche incremental)

- `info string bellman {JSON}`: `method=BELLMAN` con `visits`, `W`, `D`, `L`, `Q`, `S` o `method=NNUE` con `score_cp`, `depth` y `nodes`. JSON compacto para análisis sin afectar UCI.
- Para consultas a tabla se envía `info depth 0 nodes 0 time ...` **sin `score cp`**: no existe transformación calibrada desde WDL a centipeones.
- Los resultados de métodos diferentes se identifican en `moves.csv`; los totales se identifican en `summary.csv`. No calcula NPS cuando todas las decisiones proceden de tabla.
- `Q` es media suavizada de WDL; `S` incluye la penalización de incertidumbre.
- Este parche modifica cuatro archivos; aplicar sobre la raíz Akkad.
- No modifica la decisión de juego ni el criterio de selección de BellmanR.
