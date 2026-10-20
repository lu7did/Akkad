# v0.6.75 — MATCH/RALLY telemetría

- `--verbose` gobierna `⚙️ Argumentos` y los tres mensajes de creación, log y UCI ready de MATCH.
- Sin `--verbose` permanecen el inicio, la finalización de cada partida y el marcador final.
- El marcador final suprime `Winner` y muestra identidades en orden A/puntuación A | puntuación B/B, sin reordenación.
- Corrige referencia residual `progress.end` en cierre de partida, reemplazándola por una impresión normal.
- RALLY pasa `--verbose` a MATCH solamente si fue solicitado y oculta sus propios argumentos sin él.
- No se alteran la búsqueda, los límites, el preflight, CSV ni PGN.
