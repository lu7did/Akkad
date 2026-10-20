# Sargon-NNUE v0.6.9

## Player CEREBRUM nativo

- `CEREBRUM` deja de heredar `SARGON`.
- Implementa un player propio de horizonte fijo equivalente a 1 ply: evalúa exhaustivamente todas las jugadas legales y elige el mejor hijo.
- Resuelve checkmate y terminaciones/draws antes de invocar el evaluator.
- Evalúa todas las jugadas legales; no realiza poda en este nivel.
- Si el evaluator ofrece precisión mayor que centipawns, la utiliza para ordenar hijos antes de aplicar desempates.
- Los desempates exactos favorecen promoción, jaque y captura, manteniendo reproducibilidad.
- `MoveChoice.depth` reporta siempre `1` y `nodes` es la cantidad de hijos evaluados.

## Acumuladores Cerebrum 1.1

`CerebrumV11Evaluator` mantiene el contrato estable `evaluate(board) -> int`, y agrega:

- `evaluate_detailed(board) -> CerebrumV11Evaluation`;
- `evaluate_incremental(board, parent_result) -> CerebrumV11Evaluation`.

El resultado detallado contiene:

- score entero normalizado a perspectiva blanca;
- score flotante previo al truncado a centipawns;
- salida raw desde side-to-move;
- componentes `wr` y `mt`;
- acumuladores absolutos de perspectiva blanca y negra (`acc_white`, `acc_black`);
- activaciones `l1`, `l2`, `l3`;
- snapshot del mapa de piezas usado para actualización incremental.

La actualización incremental modifica sólo las features cuya pieza/casilla cambió entre padre e hijo. Al derivar el delta de los mapas de piezas, el mismo mecanismo cubre movimiento normal, captura, en-passant, promoción, enroque y Chess960 sin lógica especial por tipo de jugada.

## Compatibilidad arquitectónica

- `CEREBRUM + CEREBRUM-1.1` usa automáticamente la ruta incremental.
- `CEREBRUM` continúa funcionando con CLASSIC, NPZ, CEREBRUM-2 o STOCKFISH mediante `evaluate(board)`.
- SARGON, SARGON-PLUS y los demás players no fueron modificados.
- El horizonte del nuevo player CEREBRUM queda deliberadamente fijado en 1 ply en esta release.
