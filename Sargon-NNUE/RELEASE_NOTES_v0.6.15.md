# Sargon-NNUE v0.6.15

## Contrato arquitectónico PLAYER / EVALUATOR

- `player=stockfish` pasa a representar explícitamente a Stockfish como motor monolítico: su búsqueda y su evaluación son internas.
- Si se selecciona `player=stockfish` y se omite `--evaluator`, el evaluator efectivo es `NULL`.
- `player=stockfish` sólo acepta explícitamente `--evaluator null`. Cualquier otro evaluator indicado de forma explícita produce error de configuración.
- `evaluator=null` es inválido para cualquier player distinto de Stockfish.
- Los demás players conservan `CLASSIC` como evaluator por defecto cuando `--evaluator` se omite.
- Se incorpora `NullEvaluator` como sentinel explícito; no evalúa posiciones y no puede usarse como evaluador real.

## Stockfish como evaluator

- Se conserva el contrato existente: Stockfish actúa como backend de evaluación de los players componibles mediante su NNUE y el comando `eval`.
- No se agregan modos de búsqueda por depth/nodes/movetime al evaluator Stockfish.
- Se mantiene el fallback excepcional ya existente para posiciones en jaque, donde el comando `eval` de Stockfish no entrega `Final evaluation`.

## Stockfish como player

- Stockfish deja de compartir el mismo wrapper operativo que los UCI genéricos.
- Se agrega `StockfishUCIPlayer`, que usa la búsqueda interna de Stockfish con límites simultáneos de profundidad y nodos.
- `--depth` tiene default dinámico: `2` para SARGON/CEREBRUM y `20` para `player=stockfish`.
- Se agrega `--nodes`; para Stockfish el default es `5,000,000`.
- Se agrega `--elo`; el default efectivo es `max`, que desactiva `UCI_LimitStrength` y usa la fuerza completa del motor.
- Un `--elo N` explícito activa `UCI_LimitStrength` y configura `UCI_Elo=N`, validando el rango anunciado por el propio ejecutable UCI.
- `--movetime` continúa siendo usado por `sunfish` y `external`, pero es ignorado por `player=stockfish`.

## Política de parámetros irrelevantes

- Los parámetros operativos que no aplican al player/evaluator seleccionado se aceptan y se ignoran cuando no generan conflicto ni inconsistencia.
- Las combinaciones explícitas que contradicen el contrato arquitectónico sí producen error.
