# Sargon-NNUE v0.6.74 — MATCH/RALLY sin animación

Reemplazar los dos archivos en `src/sargon_nnue/`.

- MATCH escribe una línea al iniciar cada partida con `(IN_PROGRESS)` y otra al finalizar con movimientos, tiempo, resultado y motivo.
- Cada línea se imprime una sola vez, sin `\r`, sin hilos de animación, sin parpadeos.
- RALLY muestra las líneas de MATCH en orden de llegada y no reescribe líneas anteriores.
- Se mantienen preflight, tratamiento UTF-8, configuración, CSV, PGN y búsqueda de v0.6.72.
- `--verbose` sigue controlando los mensajes por jugada, sin alterar estas líneas de inicio y cierre.

Verificación: compilación sintáctica Python. No se ha probado en Windows con una partida completa.
