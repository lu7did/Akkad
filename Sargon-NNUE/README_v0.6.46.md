# Sargon-NNUE v0.6.46 — auditoría posicional durante MATCH

Este parche actualiza únicamente `src/sargon_nnue/sargon_match.py` y `src/sargon_nnue/sargon_judge.py`.

## MATCH

Argumentos nuevos:

- `--audit-stockfish-path PATH`: activa la auditoría con un proceso Stockfish UCI separado del jugador o evaluador.
- `--audit-stockfish-depth 12`: profundidad de la búsqueda de referencia.
- `--audit-stockfish-threads 1`: hilos Stockfish de auditoría.
- `--audit-network CHECKPOINT.npz`: red a medir; optativo si una sola red NPZ está definida entre A y B.
- `--audit-csv FILE.csv`: archivo posicional separado (obligatorio al activar auditoría).

Ejemplo (rutas a adaptar):

```powershell
python -m sargon_nnue.sargon_match `
  --a-player sargon-plus --a-evaluator classic `
  --b-player sargon-plus --b-evaluator npz --b-network '..\data\nnue\sf_shuffle20\nnue_epoch_004.npz' `
  --pairs 15 --csv '..\data\match.csv' --pgn '..\data\match.pgn' `
  --audit-stockfish-path 'C:\ruta\a\stockfish.exe' `
  --audit-stockfish-depth 12 --audit-csv '..\data\match_positions.csv'
```

Se registra la posición **después** de cada jugada ejecutada. Se omiten posiciones terminales (mate/tablas); no se atribuye un WDL Stockfish inexistente. El CSV incluye `game`, `pair`, `ply`, `move_uci`, FEN, fase, color de los jugadores, identificador de la red, profundidad de la búsqueda, WDL de Stockfish (perspectiva blanca), expectativa WDL Stockfish, expectativa de la red y diferencias. El proceso de auditoría no participa en las decisiones UCI de los jugadores, pero **añade tiempo real a la ejecución** y por tanto puede afectar a motores que usen controles de reloj dependientes del tiempo de pared. Las estadísticas de duración de MATCH incluyen ese sobrecoste.

La fase se clasifica mediante una heurística explícita de material no-peón y número de jugada, no mediante un clasificador aprendido.

Los errores de auditoría producen una partida incompleta y no se reemplazan silenciosamente por un valor inventado. Si el motor Stockfish no emite `wdl`, se informa el error.

## JUDGE

```powershell
python -m sargon_nnue.sargon_judge --input '..\data\match.csv' --positions '..\data\match_positions.csv'
```

La salida conserva el análisis de partidas anterior y agrega: MAE, MSE, RMSE, sesgo, correlación de Pearson (cuando está definida), acuerdo de ventaja para posiciones con |SF - 0.5| >= 0.05, y las cinco posiciones de máximo desacuerdo, globalmente y por fase.

Los valores WDL se expresan desde la perspectiva de las blancas. Este análisis mide fidelidad al Stockfish de referencia, no fuerza ajedrecística directamente.

## Verificación

- Sintaxis Python de ambos archivos: comprobada.
- JUDGE probado con un CSV sintético de partidas y un CSV sintético de posiciones.
- MATCH + Stockfish + checkpoint NPZ: **no ejecutado integralmente en este entorno**, dado que no se dispone del runtime de motor configurado por el usuario.
