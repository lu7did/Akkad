# Sargon-NNUE v0.6.17

## SARGON + Stockfish evaluator

- `player=sargon` + `evaluator=stockfish` usa **iterative deepening seguro**.
- Sólo una iteración raíz completamente terminada puede reemplazar a la anterior.
- Si `tmax` interrumpe una profundidad, los resultados parciales de esa profundidad se descartan y se conserva la última profundidad completa.
- En modo normal se emite `❌ GUARDRAIL SARGON time ...` cada vez que el límite temporal impide completar la profundidad intentada.
- El `MoveChoice.depth` reporta la profundidad realmente completada.
- SARGON con otros evaluadores conserva su comportamiento previo; el cambio se activa específicamente para `SARGON + STOCKFISH`.

## Cache del evaluator Stockfish

- Cache LRU de evaluaciones estáticas, default `100000` posiciones.
- Nueva opción `--stockfish-cache N`; `0` desactiva el cache.
- La clave conserva posición, turno, enroques, en-passant y halfmove clock; excluye sólo fullmove number.
- Los cache hits no vuelven a consultar el subprocess Stockfish.

## Telemetría normal

Al construir cada engine se muestra en stderr una línea `⚙️ EXEC` con los valores efectivos y sus defaults relevantes: player/evaluator, depth, qdepth, tmax, límites de Stockfish, ELO, threads, hash, cache y rutas aplicables.

## Stockfish como player

- `--nodes 0` significa **sin límite de nodos**.
- Si nodes=0 el comando enviado es `go depth N`, sin un segundo límite que pueda cortar la búsqueda antes de la profundidad objetivo.
- Nuevos parámetros `--stockfish-threads` (default 1) y `--stockfish-hash` (default 256 MB).
- `MultiPV=1` se fuerza explícitamente.
- Se incluye `scripts/stockfish_player_full.ps1`, configurado para `player=stockfish`, `evaluator=null`, `depth=20`, `nodes=0`, `elo=max`, `Threads=1`, `Hash=256` y watchdog UCI de 120 s.
