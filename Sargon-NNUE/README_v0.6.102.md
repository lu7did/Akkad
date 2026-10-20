# Sargon-NNUE v0.6.102 — RALLY: contador de incidencias en resumen final

Reemplazar únicamente `src/sargon_nnue/sargon_rally.py`.

Corrección acotada: `print_final_standings` vuelve a imprimir `⏰(nnn)` en cada fila del resumen que aparece **al terminar** RALLY, usando `abnormal_terminations` (o, para archivos antiguos, `ranking.resultados` + `match_incidents`). El comando `--scores` ya lo imprimía y no se modifica.

Una incidencia se atribuye a ambos brains. No se contabiliza como puntos ni como victoria, derrota o tabla. `match_incidents` no se vuelve a sumar si existe `abnormal_terminations`.

No se modifica la ejecución, persistencia, preflight ni cálculo de puntuaciones.
