# picoPixie ARM v0.1.26 -- configuracion independiente

**Configuracion propia**: `picoPixie/ARM/include/config.hpp`.
Desde ese archivo se definen `UCI_NAME`, `PORT` (6210 por defecto),
`MDNS_HOSTNAME`, `MDNS_SERVICE_NAME`, `THROTTLE` (15000 ms),
`TIMEOUT_MS` (15000 ms, limite temporal de respaldo), `DEPTH` (32),
`QDEPTH` (2). La cadencia CLOUD se mide entre inicios de consultas HTTP,
y una respuesta lenta se espera; la cadencia por si sola no activa NNUE.

**Configuracion compartida**: `picoSargon/ARM/include/config.h` proporciona
Wi-Fi (SSID/clave), PLL, UCI/DEBUG, reintentos y habilitacion de mDNS.
Los parametros homonimos del namespace picoLichess tienen prioridad solamente
cuando se compila picoPixie. El firmware picoSargon original no cambia.

El respaldo utiliza la misma busqueda, representacion NNUE, TWINS y STEROIDS
que picoSargon, con presupuesto `TIMEOUT_MS` propio y profundidad `DEPTH`
propia. `QDEPTH` se aplica a ambos nucleos del respaldo.

Ejecutar `./build.ps1` desde `picoPixie/ARM` sin argumentos; salida unica
`picoPixie/ARM/build/picoLichess.uf2`.


## Infraestructura

CMake reutiliza directamente `picoSargon/ARM/src/{pico_main,board,engine,grumpy}.cpp` y las cabeceras / blobs NNUE del proyecto compartido. Las opciones de compilacion STEROIDS y TWINS siguen activadas. El cliente HTTPS, politica de cadencia y selector de variantes permanecen en `picoPixie/ARM`.


## Remote modes (v0.1.10)
Set `MODE` in `include/config.hpp` to `Mode::CHESS_API` (default, Stockfish REST POST) or `Mode::LICHESS` (original cloud-eval GET). Both share the global `THROTTLE` in milliseconds. Chess API POST sends the board FEN, variants=5, depth=18, maxThinkingTime=100 and searchmoves=""; only `type=bestmove` is accepted. `VERBOSE=true` dumps the complete returned JSON; HTTP non-200 responses continue to log their raw received bytes. Local NNUE remains the fallback. The former `picolichess_config.hpp` is now a compatibility forwarding header for the shared picoSargon build hook.


## Evaluation slots (v0.1.17)

`include/config.hpp` declares four compile-time priority slots, for example
`{"chess-api", "lichess", "stockfish", "native"}`. Allowed unique engines are
`chess-api`, `lichess`, `stockfish`, `native` and `null` (`null` may repeat).
Each position is evaluated in priority order: the first valid and legal answer
wins; HTTP/JSON/TLS errors advance to the next slot; `native` uses the shared
picoSargon NNUE; `null` is skipped. If all slots fail, UCI reports
`info string error no-evaluator-available` and `bestmove 0000`.

URLs are configurable as full `https://...` endpoints in `config.hpp`.
`stockfish.online` uses GET v2 with `fen`, `depth` (1..15) and an optional
`STOCKFISH_KEY` passed as `key`. Leave the key empty for anonymous access.
`evaluation` is expressed in pawns and converted to centipawns (`score cp`);
`mate` is handled as `score mate`. This provider does not supply nodes/nps,
so they remain 0. `time` is the entire request-to-response wall time.

`THROTTLE` is **global** and measures request-start to request-start, not
response-to-request. It applies across online slots and successive positions.
`TIMEGUARD` disables only Lichess after HTTP 4xx; other slots continue.
The guard survives UCI sessions but holds no game state. Each HTTPS exchange
uses fresh request/response buffers. `VERBOSE=true` logs priority, requests,
full response bodies and fallback reasons; `false` retains UCI result lines.
The firmware does not duplicate picoSargon search code: its ARM sources are
compiled directly and the existing local UCI overlay is generated at build.
