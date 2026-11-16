# picoAlpha Teacher v0.1.13 — Stockfish crash quarantine

Aplicar sobre v0.1.12 descomprimiendo el ZIP en la raíz `akkad`.

## Problema observado

`Stockfish` finaliza con `EngineTerminatedError` (`exit code: 1`) en la misma posición incluso luego de reiniciarse tres veces. No puede concluirse del error que el FEN sea inválido: también pueden intervenir el ejecutable, los recursos o un bug del motor.

## Comportamiento corregido

- `RestartableEngine` intenta inicialmente una evaluación, luego hasta `--engine-retries` reinicios para esa posición. Después de agotar los intentos, produce `EnginePositionFailure` y deja el proceso muerto descartado; **no termina el lote por una sola posición**.
- `teacher.py` registra el `id`, el FEN y el error de esa posición en una tabla adicional `teacher_quarantine`, dentro del mismo archivo SQLite `.pb`. No modifica ni borra esa fila en `positions` y no falsifica una evaluación.
- En la siguiente posición se inicia una instancia nueva de Stockfish.
- `--resume` recorre **todas** las posiciones con su barra habitual; salta filas que tengan evaluación completa y aquellas registradas en `teacher_quarantine`. Muestra `already_labeled`, `quarantined` y `pending`.
- Un circuito de seguridad **detiene el proceso tras cinco posiciones consecutivas** que agoten sus reintentos. Esto protege la base de millones de cuarentenas si el problema es general y no localizado.
- Las evaluaciones correctas se confirman individualmente en SQLite, como anteriormente. Si una posición en cuarentena vuelve a evaluarse con éxito ejecutando sin `--resume`, su entrada de cuarentena se elimina.
- La lógica de FEN inválido y de respuestas numéricas UCI incoherentes es la existente en v0.1.10 y no fue alterada.

## Ejecución

```powershell
cd C:\Users\pedro\github\bobby\akkad\picoAlpha\tools\train
.\run_genesis.ps1 -Mon 3 -Resume
```

Si deseas auditar qué posiciones fueron colocadas en cuarentena:

```python
import sqlite3
with sqlite3.connect(r'C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\sample_history.pb') as db:
    for item in db.execute('SELECT position_id, fen, reason, attempts FROM teacher_quarantine ORDER BY position_id'):
        print(item)
```

La tabla no elimina datos previos. `teacher.py` no altera `run_genesis.ps1` en este parche. **No se ha confirmado todavía la causa concreta de la salida de Stockfish (exit code 1)**; se recomienda inspeccionar el ejecutable, los recursos y el FEN registrado si reaparece.

## Validación

29 pruebas automatizadas completadas, entre ellas reinicios, reanudación, conservación de filas, descarte lógico, cuarentena, límite de fallos consecutivos y recuperación. No se ejecutó Stockfish real bajo Windows.
