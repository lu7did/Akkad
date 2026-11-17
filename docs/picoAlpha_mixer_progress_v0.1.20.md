# picoAlpha mixer v0.1.20 — Telemetría de progreso en una línea

## Defecto

El `Reporter` de `mixer.py` emitía una línea nueva cuando `sys.stdout.isatty()` devolvía `False`. Algunos wrappers y entornos PowerShell provocaban este modo, haciendo que la barra de progreso ocupara cientos de líneas.

## Corrección

- Una única línea activa por fase (`INDEX MIX`, `PARTIDAS`, `MEZCLA`), actualizada mediante retorno de carro `\r` en todos los entornos.
- Salto de línea `\n` exclusivamente al terminar cada fase (o si se cambia de fase sin completar la anterior).
- Se elimina texto residual si la línea nueva es más corta, con espacios de relleno.
- Actualizaciones limitadas a como máximo cinco por segundo, salvo inicio y finalización.
- La llamada redundante de finalización no duplica la línea del 100 %.
- Se conservan contadores, restantes, velocidad, ETA y reutilización de etiquetas.

Los archivos de log redirigidos conservarán retornos de carro. No se recomienda interpretar cada retorno de carro como una línea nueva.

## Pruebas

`python -m unittest discover -s tests -p test_mixer.py -v`: 6 pruebas superadas, incluida salida simulada con `isatty() == False` y comprobación de un único salto de línea por fase.

## Alcance

Sin cambios al algoritmo de mezcla, esquema SQLite, opciones CLI ni wrapper PowerShell.
