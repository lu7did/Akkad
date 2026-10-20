# Sargon-NNUE v0.6.7

## Nuevo evaluator STOCKFISH

Se incorpora `--evaluator stockfish` como adapter independiente del player.  El
player (por ejemplo `SARGON`) continúa consumiendo únicamente el contrato común
`evaluate(board) -> centipawns desde perspectiva blanca`.

El evaluator mantiene un proceso Stockfish persistente por sesión, configura la
red indicada con `EvalFile`, envía `position fen ...` + `eval` y toma únicamente
`Final evaluation`, que Stockfish reporta desde la perspectiva de blancas.

### Posiciones excepcionales

- checkmate: resuelto localmente con `MATE_CP`;
- tablas terminales: `0`;
- jaque no terminal: Stockfish `eval` devuelve `none (in check)`, por lo que se
  usa excepcionalmente `go depth 1` (configurable con
  `--stockfish-check-depth`) y se normaliza el score UCI a perspectiva blanca.

La búsqueda de fallback sólo existe para sortear la limitación explícita del
comando `eval`; las posiciones normales se evalúan exclusivamente mediante
`Final evaluation`.

### CLI

- `--evaluator stockfish`
- `--network <archivo.nnue>`
- `--stockfish-path <stockfish.exe>`
- `--stockfish-timeout <ms>` (default 5000)
- `--stockfish-check-depth <n>` (default 1)

Se agrega `scripts/sargon_stockfish_eval.ps1` como ejemplo.

## Ciclo de vida

Los evaluators ahora poseen `close()`.  El listener cierra explícitamente el
evaluator de cada sesión, evitando procesos Stockfish huérfanos al desconectar
un cliente o terminar el servidor.

## Integración transversal

`STOCKFISH` también queda disponible en `sargon-selfplay` mediante los argumentos
prefijados (`--white-evaluator stockfish`, `--white-stockfish-path ...`, etc.) y
en `sargon-train` para evaluación de PGN. Como todo evaluator externo, rechaza
entrenamiento local. Tanto listener como selfplay y train cierran explícitamente
sus procesos backend al finalizar.
