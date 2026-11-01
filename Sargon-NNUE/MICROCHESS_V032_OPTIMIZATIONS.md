# Microchess v0.3.2 — optimización sin cambios de política

Sargon-NNUE 0.6.196. Parche incremental sobre v0.3.1.

- `PieceTable` conserva la tabla de posiciones como estado primario e incorpora `_occupancy` derivado para consultar ocupantes en O(1). `push/pop` actualizan y restauran el índice, incluidas capturas, promoción, enroque y captura al paso.
- `Janus.candidate(..., previous=...)` acepta las estadísticas P precomputadas. El player conserva una caché por FEN y bando **por decisión**, que evita calcular `PMOB/PMAXC/PCC` para cada candidato de esa posición.
- `gnm()` crea una sola instantánea de movimientos legales por invocación; admite `legal_moves` precomputados y evita recorrer `board.legal_moves` dos veces. TREE comparte esa instantánea con GNM para el mismo estado.
- `measure()` utiliza directamente la tabla de piezas y el índice de ocupación sin consultas repetitivas a `board.piece_at()`.
- `last_metrics` agrega `reference_cache_hits`, `reference_cache_misses`, `reference_cache_entries`, `measure_time_ms`, `gnm_time_ms` y `tree_time_ms`. Los tiempos son acumulados por operación y se pueden solapar con `janus_time_ms`; no deben sumarse como tiempos independientes. `gnm_time_ms` mide invocaciones a `gnm`, no el recorrido geométrico interno realizado directamente por `measure`.
- No se modifican STRATGY, la profundidad de TREE, el orden de candidatos ni las ponderaciones del evaluador.

## Validación

Se comprobó sintaxis e integridad del ZIP. Se incluyen pruebas unitarias nuevas para el índice de ocupación, reversibilidad y equivalencia de cálculo con/sin estadísticas precomputadas. No fue posible ejecutarlas en el entorno de creación debido a la ausencia de `python-chess`. Ejecutar en el venv del proyecto:

```powershell
python -m pytest tests/test_microchess_optimizations_v032.py tests/test_microchess_metrics_v031.py -q
```

Los contadores de nodos conservan la semántica previa; no deben equipararse con nodos del motor picoSargon C++.
