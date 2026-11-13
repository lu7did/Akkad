# picoAlpha Training v0.1.5 — Progreso en consola

## Alcance

- `common.progress()` es la interfaz común de `sampler.py`, `teacher.py` y `train.py`. Cuando stdout es una terminal interactiva, emite `\r` y sobrescribe **la misma línea**; imprime `\n` exclusivamente al completar la etapa (o al cambiar a otra).
- Las barras tienen 24 columnas, porcentaje con dos decimales y contadores alineados al ancho del total. El texto complementario también mantiene ancho fijo.
- Cuando stdout no es una terminal (redirección, tubería o CI), suprime las actualizaciones intermedias y emite solo una línea final por etapa, sin secuencias de control.
- `sampler.py` presenta una barra completa incluso con `--sample 0`.
- `loader.py` conserva su diseño anterior con **dos líneas fijas** porque informa archivos y partidas simultáneamente. No se modificó su lógica de importación.
- `create.py` y `export.py` no tienen bucles con progreso que requieran barra.

## Compatibilidad

Esta entrega modifica solamente la telemetría de los pasos; no altera los algoritmos de muestreo, etiquetado, entrenamiento o exportación. Se aplica a la raíz `akkad/` sobre picoAlpha v0.1.4.

## Pruebas

`python -m unittest discover -s picoAlpha/tools/train/tests -v`

Incluye pruebas de terminal simulada, redirección, ancho fijo, transición entre etapas y muestreo de cero partidas.
