# Sargon-NNUE v0.6.16 — diagnóstico Stockfish

## Objetivo

Versión de diagnóstico derivada de v0.6.15. No cambia la lógica de decisión de los motores; agrega trazabilidad para localizar el fallo observado en partidas con Stockfish.

## Auditoría

- `--audit` habilita registro JSONL.
- `--audit-file FILE` selecciona el archivo.
- `--audit-eval-max N` limita el número de evaluaciones Stockfish detalladas registradas por sesión.
- Se registran comandos UCI de entrada/salida, FEN reconstruido, cada `go`, la jugada elegida y transmitida, configuración efectiva y telemetría completa del player Stockfish.
- Cuando Stockfish actúa como evaluator se registra FEN, turno, modo (`eval` o fallback en jaque), score en centipawns desde perspectiva blanca, tiempo y salida cruda asociada.

## Script de prueba

`scripts/sargon_stockfish_audit.ps1` separa explícitamente:

- `-Mode stockfish-player`: Stockfish player + evaluator NULL, con StockfishDepth=20 y StockfishNodes=5000000 por defecto.
- `-Mode stockfish-evaluator`: Sargón player depth=3 + Stockfish evaluator.

Esto corrige para la prueba un problema de configuración detectado en `sargon_stockfish.ps1` v0.6.15: ese script tenía `Depth=3` como default y lo transmitía también cuando `Player=stockfish`, anulando de hecho el default dinámico depth=20 definido por el programa.

## Analizador

`scripts/analyze_stockfish_audit.py FILE` resume configuración efectiva, profundidad/nodos reales, bestmoves y discrepancias entre jugada interna y jugada transmitida.
