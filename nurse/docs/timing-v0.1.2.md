# Nurse v0.1.2 — Contrato temporal uniforme

Todos los `brains` (`nurse`, `uci` y `external`) admiten los mismos campos temporales **en milisegundos**:

- `tmax`: presupuesto **máximo de análisis por jugada**. Default `15000`.
- `timeout`: margen máximo de **comunicación** (handshake UCI, solicitud inicial y tolerancia luego del presupuesto de análisis). Default `30000`. **No es el tiempo de pensamiento.**
- `warmup_movetime`: **igual a `tmax`**. Se deriva automáticamente si no está declarado; si aparece con un valor distinto, se rechaza la configuración.

Ejemplo:

```json
"fishy": {
  "type":"uci",
  "player":{"windows":"../../../stockfish/stockfish.exe","debian":"/usr/games/stockfish","macOS":"/usr/local/bin/stockfish"},
  "evaluator":"null", "tmax":1000, "timeout":30000, "ELO":3000
}
```

Un comando UCI `go` se normaliza a `go movetime <tmax>`. `go movetime X` usa `min(X,tmax)`; `go depth D` retiene la profundidad, pero también agrega límite temporal. `go infinite`, `ponder` y controles de reloj se convierten a búsqueda acotada. Los procesos externos tienen tiempo de cortesía de comunicación después del presupuesto máximo: la espera total de `bestmove` está limitada a `tmax + timeout` (más gastos de infraestructura). Este es un límite del **supervisor**; si el motor no coopera con `movetime`, Nurse informa el fallo y cierra su conexión.

Los workers Python reciben `tmax` para sus algoritmos con control cooperativo del tiempo. No se promete terminación preemptiva de algoritmos Python que no examinan ese límite; ante falta de respuesta, Nurse descarta el proceso y no lo reutiliza. `timeout` no se utiliza para decidir cuánto deben pensar.

## Calentamiento

Por definición `warmup_movetime=tmax`: **el calentamiento puede consumir el presupuesto completo**, incluso si es Bratko–Kopec. Si se solicita la prueba histórica con `--bratko-kopec --bk-movetime 120`, el benchmark pasa `--tmax 120000` a ese proceso Nurse, y el calentamiento también puede durar 120 segundos. Para una prueba rápida usar `--warmup 0` o reducir explícitamente `--bk-movetime`; no es una regresión ni un bloqueo.

`nurse.benchmark` reserva una espera de supervisor por jugada superior a `tmax + timeout` para no declarar timeout de su cliente mientras Nurse todavía cumple su contrato. `match` y `rally` usan `go` sin límite explícito, que Nurse limita a `tmax`.

Los cambios no alteran Sargon-NNUE, únicamente `nurse`.
