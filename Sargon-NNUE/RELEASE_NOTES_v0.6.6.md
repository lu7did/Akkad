# Sargon-NNUE v0.6.6

## Corrección de infraestructura: cierre por Ctrl+C

- El listener TCP ya no depende de un `accept()` bloqueante indefinidamente.
- Se instala manejo explícito de `SIGINT`/`SIGTERM`.
- `Ctrl+C` marca la parada, cierra el socket de escucha y todas las sesiones activas.
- `accept()` usa timeout corto para garantizar que el loop observe la parada aun en Windows.
- El cierre de threads de sesión es acotado y no puede bloquear indefinidamente la terminación.
- No se modifican evaluators, players ni lógica de juego.
