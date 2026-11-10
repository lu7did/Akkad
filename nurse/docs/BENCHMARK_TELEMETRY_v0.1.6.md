# Nurse v0.1.6 — benchmark: conservación de telemetría y presupuesto

- Consola: una línea por posición evaluada: índice, turno, bestmove, tiempo, nodos y estado. No imprimir banner por posición ni heartbeat de bestmove ni duración de calentamientos.
- Calentamiento: `warmup_movetime=tmax` DEL BRAIN, sin sobrescribirlo por el presupuesto histórico Bratko–Kopec. Para omitirlo `--warmup 0`.
- Bratko–Kopec: `--bk-movetime` solicita tiempo en segundos pero **no puede aumentar `brain.tmax`**. Tiempo efectivo `min(--bk-movetime*1000, brain.tmax)`; el `manifest.json` registra ambos. Para reproducir 120s hay que configurar `tmax>=120000` explícitamente.
- `timeout` mantiene su rol de límite de comunicación; no regula la búsqueda.
- Los motores UCI se presentan por nombre del ejecutable (o `engine_name` opcional), no se atribuyen automáticamente a Stockfish. Este nombre es una etiqueta local, no una identificación UCI validada.
- La telemetría completa de cada motor sigue disponible en `engine_XX.log` (stderr de Nurse), sin mezclarla con el resumen en stdout. El registro exhaustivo por línea UCI genera E/S adicional y no debe confundirse con tiempo de cómputo del motor.
- Se conserva el formato de `moves.csv`, `summary.csv`, Bratko-Kopec, matrices y reportes.
- Tests: `python -m unittest discover -s tests -v`.
