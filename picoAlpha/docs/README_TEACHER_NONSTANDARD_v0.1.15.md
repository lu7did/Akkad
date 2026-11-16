# picoAlpha teacher v0.1.15 — posiciones incompatibles con Stockfish

Cambios limitados a `teacher.py`; no se alteran las evaluaciones válidas ni el contrato de la base SQLite.

* Antes de llamar a Stockfish se mantiene `chess.Board(fen)` y `board.is_valid()`, y se añade una **condición necesaria de legalidad del material** para ajedrez convencional: las piezas adicionales (damas, torres, alfiles y caballos por encima de la dotación inicial) no pueden superar los peones ausentes. Detecta los FEN con siete alfiles y ocho peones por bando encontrados en las posiciones 3773336–3773340.
* Las posiciones con FEN inválido o material imposible se eliminan mediante el mecanismo de limpieza ya existente (misma decisión de v0.1.8). Las posiciones cuyo análisis hace caer Stockfish se **conservan** y se registran en `teacher_quarantine` (como en v0.1.13).
* Cuando se llega a cinco caídas consecutivas, se evalúa con profundidad 1 la posición inicial estándar con un Stockfish recuperado. Si funciona, se continúa con la siguiente fila; si falla, se detiene el proceso para evitar una cuarentena masiva.
* Con `--resume`, las filas ya etiquetadas o en cuarentena se cuentan sin recalcularse. Las cinco filas 3773336–3773340 previamente en cuarentena permanecerán en la base: el parche no las elimina retroactivamente ni vuelve a procesarlas en modo resume.

## Ejecución

Desde `picoAlpha/tools/train`: `./run_genesis.ps1 -Mon 3 -Resume`

## Límites

La prueba de material es necesaria, no una prueba completa de alcanzabilidad de una posición estándar. El programa no deduce ni intenta ejecutar variantes. El chequeo de control reduce el riesgo de ocultar un fallo general de Stockfish; no garantiza identificar toda causa subyacente.
