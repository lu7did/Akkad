# picoGenus / genBP.py — v0.1.17

Convierte un archivo EPD de posiciones de ajedrez ortodoxo a una base SQLite con extensión `.pb` y **el mismo esquema de `games` y `positions` que picoAlpha**. No utiliza archivos de ejemplo codificados ni datos ficticios. Cada línea EPD produce como máximo una fila en cada tabla. Cada posición se analiza con Stockfish a profundidad configurada (10 por defecto). 

## Ejecución desde `picoGenus/tools/train`

```powershell
python .\genBP.py `
  --in "..\..\assets\bratko_kopec.epd" `
  --out "..\..\assets\bratko_kopec.pb" `
  --stockfish "C:\Users\pedro\github\Bobby\stockfish\stockfish.exe" `
  --depth 10
```

`--in`, `--out` y `--stockfish` son obligatorios; `--help` presenta las opciones. `--nodes N` limita opcionalmente los nodos por posición. El programa comprueba rutas y requiere que el directorio de destino exista.

## Correspondencia con la base de picoAlpha

- `games`: una fila por posición EPD, `source_file` contiene la ruta EPD, `source_ordinal` el número de línea; `headers_json` conserva la línea EPD completa (incluyendo `bm`, si la hubiera).
- `positions`: un registro por posición, `ply=1`, FEN completo de seis campos, `teacher_uci` = mejor movimiento de Stockfish, `teacher_cp` / `teacher_mate` y `teacher_value` = `tanh(cp / 400)` en perspectiva del bando al turno, `teacher_depth` y `teacher_at`.
- Como EPD no contiene una **jugada efectivamente realizada**, `played_uci` se establece igual a la recomendación de Stockfish **solo para satisfacer el esquema obligatorio**. No debe interpretarse como jugada humana.
- Las referencias `bm` incluidas en EPD no sustituyen la evaluación del motor; quedan en `headers_json`.

Los registros con FEN inválido, material evidentemente imposible o sin jugada evaluable se descartan y contabilizan. Ante terminación inesperada del motor se reinicia y reintenta una vez; si vuelve a fallar, se prueba una posición estándar de control, para no ignorar en silencio un fallo general de Stockfish.

La telemetría se actualiza sobre **un mismo renglón**, utilizando `█` y `░`, porcentaje, registros generados y total de líneas EPD elegibles. Las columnas numéricas son de ancho fijo y la barra se ajusta al ancho de consola. Al redirigir la salida a un archivo se imprime solamente el resumen final de progreso.

La base de salida se genera en un archivo temporal contiguo y se reemplaza al finalizar correctamente y **después de cerrar SQLite**, evitando el `WinError 32` que afectó a `genSample.py`. La ruta `--out` se sobrescribe; si se produce un error o Ctrl+C, la base previa no se modifica.

## Dependencias

`pip install python-chess` (además de una instalación local de Stockfish).

No modifica `run_genesis.ps1`, `genSample.py`, `genPST.py` ni `genNNUE.py`.
