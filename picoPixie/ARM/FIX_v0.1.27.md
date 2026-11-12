# picoPixie v0.1.27 — corrección de análisis remoto de mate

## Incidente reproducido

La telemetría del 12 de noviembre de 2026 registra `stockfish` con HTTP 200, `bestmove g5f6`, `evaluation:null` y `mate:"2"` (cadena JSON). El parser exigía un `mate` numérico; al no encontrarlo, exigía una evaluación numérica y descartaba una jugada válida, pasando innecesariamente a `lichess` y posteriormente a `native`.

## Corrección

`parse_stockfish_online_response` admite `mate` como número JSON o como cadena decimal estricta dentro de límites, manteniendo validaciones de `success`, estructura JSON, formato UCI y posterior validación de legalidad en el tablero local. No altera ninguna regla de ajedrez ni conserva estado entre consultas.

## Incidencia diferente, no resuelta localmente

`chess-api` devolvió HTTP 200 con `INVALID_FEN_VALIDATION_ERROR` para `r1bqkb1r/ppppp1pp/6n1/3PPp2/4nP2/8/PPP1Q1PP/RNB1KBNR w KQkq f6 0 7`. Este FEN contiene un objetivo de captura al paso `f6` después de `f7f5`, con un peón blanco en `e5`: no debe omitirse `f6` porque modificaría el conjunto de jugadas legales. El proveedor rechazó la petición, y el fallback a otro motor fue adecuado. La respuesta no permite atribuir el rechazo a un bug de integridad en el motor local.

## Verificación

Test de regresión `tests/test_stockfish_online.cpp` con el JSON observado, más mate numérico, cadena negativa, cadena inválida y otros casos anteriores. Compilación ARM pendiente en hardware/SDK.
