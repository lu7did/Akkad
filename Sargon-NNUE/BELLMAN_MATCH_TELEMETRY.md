# Telemetría Bellman en MATCH

Agregar `--telemetry` a `python -m sargon_nnue.sargon_match` o a los argumentos del script PowerShell.

MATCH conserva las líneas `info` recibidas entre `go` y `bestmove` para cada jugada, analiza `info string bellman {JSON}` y la línea UCI convencional, e imprime un único resumen por jugada. No afecta al cálculo de la jugada ni a `--verbose`.

Los nodos reportados por Bellman son los movimientos legales examinados (no visitas históricas `N`); el NPS Bellman no es directamente comparable al NPS de alfa-beta.
