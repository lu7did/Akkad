# Telemetría de bellman_upload.py

La fase de conteo muestra una única línea dinámica: `🔎 Archivos 2/19 ( 10.5%) · 8,415 partidas detectadas · Carlsen.pgn`.

La importación muestra una única línea dinámica con contador de archivos, contador de partidas, barra, porcentaje global y archivo activo. Los contadores de nuevas/repetidas/omitidas se muestran únicamente al terminar.

Los errores de SAN registrados por `python-chess` se gestionan como juegos inválidos sin imprimir las trazas, y quedan contabilizados en `omitidas`. Se conserva la importación acumulativa y la identidad SHA-256.
