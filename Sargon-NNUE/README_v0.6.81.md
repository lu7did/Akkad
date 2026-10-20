# v0.6.81 — Corrección regresión RANDOM/NULL

Reemplazar solo `src/sargon_nnue/brains.py`.

Causa: el archivo introducido en v0.6.79 (ELO) restauró una validación antigua que rechazaba `player=random, evaluator=null`. MATCH falla antes de iniciar el motor.

Cambio único: admitir `null` para `random` y `stockfish`, y rechazarlo para los jugadores restantes. Mantiene la compatibilidad del campo `rating_elo`.

No modifica partidas, puntajes ya guardados, MATCH ni RALLY.

Comprobaciones: sintaxis Python y pruebas aisladas de `validate()` para `random|null`, `stockfish|null`, `sargon-plus|classic`, combinaciones inválidas y campo `rating_elo`. No probado en Windows.
