# picoAlpha Training v0.1.8 — tolerancia a FEN defectuosos

## Incidencia reproducida

`teacher.py` se detenía ante un FEN almacenado como `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 3+3 0 1` (campo `halfmove_clock` inválido: `3+3`). Una posición defectuosa interrumpía el etiquetado de toda la base.

## Comportamiento nuevo

- `teacher.py`: valida `chess.Board(fen)` y `board.is_valid()` **antes** de consultar Stockfish. Ante FEN inválido elimina **solo esa fila** de `positions` (`DELETE ... WHERE id=?`) y continúa. No borra la partida completa ni filas válidas. La operación es transaccional. La telemetría de la barra permanece intacta; al terminar se informan hasta ocho posiciones eliminadas con su id/FEN y un resumen de cantidades.
- `loader.py`: valida la posición inicial y todas las jugadas de una partida **antes** de escribir en la base. Si detecta una partida inválida, no importa ninguna fila de ella y la cuenta entre las descartadas. El proceso sigue con la próxima partida; la barra de progreso de dos líneas se conserva. Las partidas con errores informados por el parser PGN también se descartan.
- No se suprimen errores de Stockfish, de SQL ni de E/S: se siguen reportando como fallos genuinos.

## Reanudación

Aplicar el ZIP desde la raíz `akkad/` y continuar con `./run_genesis.ps1 -Mon 3`. Se vuelven a evaluar las posiciones válidas (conducta reentrante vigente), pero las inválidas se eliminan y dejan de bloquear el lote. No reejecutar `-Mon 0` si se desea conservar el histórico.

## Alcance y limitaciones

No se diagnostica la causa original de la cadena `3+3` a partir del log; puede provenir de encabezados PGN defectuosos o de otra fase de carga. Los archivos ya cargados con FEN malo quedan saneados por `teacher.py`. Los nuevos PGN se filtran al importar. Esta revisión no repara automáticamente un FEN recuperable; elimina la fila, según el criterio autorizado.
