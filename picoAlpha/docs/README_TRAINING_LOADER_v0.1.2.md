# picoAlpha — Loader: telemetría de dos líneas (v0.1.2)

El parche cambia **solamente** el progreso mostrado por `picoAlpha/tools/train/loader.py`.
No modifica esquema `.pb`, reglas de importación ni scripts PowerShell.

## Consola interactiva

El progreso se dibuja sobre **dos líneas persistentes** mediante códigos ANSI de posicionamiento:

```text
📁 Archivos [████████░░░░░░░░░░░░░░░░]  33.33%   1/  3 games_02.pgn
♟  Partidas [██████░░░░░░░░░░░░░░░░░░]  25.00%  50/200
```

- Primera línea: archivos **completados** / total y nombre del archivo en curso.
- Segunda línea: partidas **recorridas**, incluso partidas omitidas por errores PGN o ya importadas, / partidas del archivo actual.
- Las barras, porcentajes, denominadores y nombres usan ancho fijo; el nombre demasiado largo se acorta por la izquierda.
- Se utiliza una pasada previa con `chess.pgn.skip_game()` para contar partidas antes de importarlas. La lectura real ocurre en una segunda pasada: el doble recorrido es el coste de conocer el denominador exacto.
- En la consola interactiva se sobreescriben las mismas dos líneas. En redirección a archivo se escriben **solamente las dos líneas finales**, sin secuencias ANSI.
- Si la consola de Windows no permite habilitar secuencias VT, se evita imprimir controles ilegibles y se emiten las dos líneas finales.

## Compatibilidad

`run_loader.ps1` y los argumentos `--in` / `--out` se mantienen sin cambios. La importación sigue siendo acumulativa e idempotente. El programa no emite otras líneas durante una ejecución satisfactoria; los errores excepcionales se informan mediante excepción y salida de error.

## Validación

`python -m unittest discover -s picoAlpha/tools/train/tests -p test_loader_progress.py -v`

Cuatro pruebas del componente de telemetría superadas. No se ejecutó importación PGN real en este entorno porque no está instalado `python-chess`.
