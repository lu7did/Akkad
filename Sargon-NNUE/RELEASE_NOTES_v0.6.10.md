# Sargon-NNUE v0.6.10

## SARGON+ refactor desde base cero

- `SARGON` permanece sin modificaciones funcionales y sigue siendo el baseline canónico.
- Se elimina por completo del player `SARGON+` la profundización selectiva experimental basada en `candidates`, `step` y `dmax`.
- Se elimina ese wiring del CLI/factory.
- `SARGON+` parte de la búsqueda SARGON y añade **Iterative Deepening** como comportamiento base.
- Se introduce `--boost N`, con `N=0..13`, acumulativo. Cualquier semántica previa de `--boost` queda descartada.

## Escala de `--boost`

| N | Optimización nueva en ese nivel |
|---:|---|
| 0 | Iterative Deepening |
| 1 | History Heuristic |
| 2 | Killer Moves |
| 3 | PVS / NegaScout |
| 4 | TT con bounds EXACT / LOWER / UPPER |
| 5 | Hash move first |
| 6 | SEE real + SEE pruning |
| 7 | Aspiration Windows |
| 8 | Late Move Reductions (LMR) |
| 9 | Futility + Reverse Futility |
| 10 | Delta pruning en quiescence |
| 11 | Razoring |
| 12 | Null Move Pruning |
| 13 | ProbCut + MultiCut |

Cada nivel incluye todos los anteriores. Ejemplo: `--boost 6` activa niveles 0 a 6.

## Criterio de aislamiento

Los niveles 0, 1 y 2 conservan el minimax/alpha-beta canónico de SARGON y sólo agregan respectivamente iterative deepening y ordenamiento History/Killer. A partir de nivel 3 se utiliza el núcleo PVS. Esto evita que las primeras comparaciones mezclen una transformación del algoritmo con las heurísticas de ordenamiento.
