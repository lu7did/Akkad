# Sargon-NNUE v0.6.8

## Cambio

- El evaluator `STOCKFISH` ya no exige `--network`.
- Si `--network` se omite, Sargon-NNUE no envía `setoption name EvalFile ...`; Stockfish conserva su red default/embebida.
- Si `--network` se informa, se mantiene el comportamiento de v0.6.7: se valida el archivo y se selecciona explícitamente mediante `EvalFile`.
- `--stockfish-path` continúa siendo obligatorio.
- `sargon-train.py` conserva el default `data/nnue/checkpoint.npz` sólo para evaluator NPZ; no lo inyecta al evaluator STOCKFISH.
- El script `scripts/sargon_stockfish_eval.ps1` deja `-Network` vacío por default y sólo transmite `--network` cuando el usuario lo informa.

No se modificaron players, búsqueda, quiescence, scores, concurrencia ni protocolo de evaluación `Final evaluation`.
