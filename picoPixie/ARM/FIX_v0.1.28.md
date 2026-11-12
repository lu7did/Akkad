# picoPixie v0.1.28 — FEN íntegro y compatibilidad de proveedores

**Origen**: telemetría del 12/11/2026, partida con `d2d4 ... f7f5`.

La posición `r1bqkb1r/ppppp1pp/6n1/3PPp2/4nP2/8/PPP1Q1PP/RNB1KBNR w KQkq f6 0 7` es válida: la captura al paso `e5f6` es legal. Los dos rechazos de `chess-api` corresponden a esa **misma** posición. El proveedor contesta HTTP 200 con `INVALID_FEN_VALIDATION_ERROR`; el código ya canonizaba objetivos EP no capturables, pero no debe suprimir un objetivo EP legal.

**Corrección de la causa del fallo de integración**: `picolichess_adapter.cpp` omite el slot `chess-api` cuando `Board::position_key().ep >= 0` (captura al paso *legalmente* disponible), registrando `reason=unsupported-legal-en-passant`. Se avanza al siguiente proveedor manteniendo el FEN exacto, sin agotar ni activar el TIMEGUARD del slot, que sigue disponible para otras posiciones. Stockfish, que en la telemetría sí aceptó el mismo FEN y devolvió `e5f6`, conserva el derecho de analizar esa posición. No se alteran núcleo ni algoritmos de picoSargon.

**Alcance y limitación**: es una mitigación específica basada en el fallo reproducido del contrato de interoperabilidad con chess-api; no demuestra que chess-api rechace *todos* los FEN con captura al paso legal, ni que este sea el único motivo de rechazo de FEN. No se realizaron solicitudes externas (según la restricción de la línea de base). La compilación ARM requiere Pico SDK y la cadena correspondiente.

**Regresión**: `test_fen.cpp` reconstruye las doce jugadas observadas, coteja el FEN exacto, confirma que `e5f6` es legal y que chess-api queda inelegible; prueba también EP no capturable. Aplicar ZIP desde raíz de Akkad sobre v0.1.27.
