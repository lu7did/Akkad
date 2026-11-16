# picoGenus PST v0.1.16 — refinamientos puntuales desde ChessGP

Referencia secundaria: Damián Kružliak, tesis *Genetic algorithms for evolving chess evaluation functions* (2026), código de `ChessGP/src/ChessGP.Core/Eval/ParametricEvaluator.cs`, https://github.com/Inval1dka/chessgp .

## Contrato de fidelidad

- Conserva el cromosoma del artículo de David et al.: **34 genes evolucionables, 4 × 11 + 30 × 6 = 224 bits**, peón fijo en 100 cp, codificación Gray.
- **No cambia** la búsqueda 1-ply, `fitness = aciertos ** 2`, selección, cruzamiento, mutación ni elitismo; tampoco `genPST.py`, `genNNUE.py`, Nurse ni los scripts PowerShell.
- El evaluador Nurse reutiliza `gen_pst_core.py`, por lo que hereda automáticamente estos refinamientos.
- No añade genes, parámetros ni fórmulas sin equivalencia directa con el diseño original.

## Tres detalles preexistentes completados

1. `BACKWARD_PAWN_PENALTY`: `_backward_pawn` ahora requiere que **la casilla frontal esté libre**, además del apoyo lateral y el ataque del peón adversario ya exigidos. Fuente: `IsBackwardPawn`, `ParametricEvaluator.cs`.
2. `ROOK_BEHIND_PASSED_PAWN`: la torre propia debe estar detrás de un peón pasado propio **con todas las casillas intermedias vacías**. Fuente: `IsBehindAnyPassedPawnOnFile` y `ClearFileLine`.
3. `ROOK_ATCK_WEAK_PAWN_OPEN_COLUMN`: exige **línea despejada entre torre y peón enemigo débil**, manteniendo los criterios de debilidad y columna preexistentes en picoGenus. Fuente: `AttacksWeakPawnOnFile` y `ClearFileLine`.

## Deliberadamente sin cambios

`ROOK_CONNECTED` ya exigía alineación y trayecto libre; se conserva. `WEAK_SQUARE_PENALTY` usa una definición diferente (control enemigo y falta de defensa por peones), por lo que sustituirla alteraría la heurística: sin cambios. `ROOK_COLUMN_MULT`, `ROOK_ATTACK_KING_ADJ_FILE_ABGH` y términos de seguridad del rey carecen de equivalencias **idénticas** en ChessGP: sin cambios. No se incorporaron `TempoBonus`, bonificaciones por peones pasados protegidos/conectados ni otros genes de ChessGP.

La tesis y el código ChessGP no prueban que estas tres fórmulas sean idénticas al evaluador original de los autores de David; son detalles operativos trazables de una implementación secundaria, sin cambiar el significado ni el conjunto de genes.

## Pruebas

`python -m unittest discover -s picoGenus/tools/train/tests -p 'test_pst_chessgp_details_v0116.py' -v` desde la raíz de Akkad. Requiere `python-chess` y `numpy`. Incluye pruebas de casilla frontal libre, bloqueo en líneas de torre, efecto de los coeficientes y esquema Gray.
