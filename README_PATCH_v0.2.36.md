# picoAlpha v0.2.36 — UCI simplificada

Parche incremental **sobre v0.2.35**. Modifica solo `picoAlpha/src/pico_main.cpp`.

- Actualiza `VERSION` a `picoAlpha v0.2.36`.
- Sustituye `info nodes N time T` por `info move M nodes N time T sims S`, con valores efectivos de cada búsqueda.
- `M` proviene de `Board::fullmove`, el número de jugada ajedrecística (1 para ambos turnos de la primera jugada, 2 para ambos de la segunda, etc.). Es compatible con posiciones iniciales FEN.
- Elimina el mensaje redundante `info string mcts simulations=... tree_nodes=... tree_capacity=... growth_events=...`.
- Conserva `bestmove` y las otras líneas de telemetría.

**Compatibilidad UCI:** `info move` y `sims` son campos personalizados, no parámetros estándar del comando UCI `info`; algunos clientes pueden ignorarlos. `nodes`, `time` y `bestmove` siguen siendo estándar.

No se cambia MCTS, NN, memoria, el doble núcleo ni los límites de simulaciones.
