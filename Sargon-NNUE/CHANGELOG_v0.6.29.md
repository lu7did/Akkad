# Sargon-NNUE v0.6.29 — Diagnóstico de entrada .pb

## Correcciones
- `pb_data.connect(create=False)` abre el .pb en modo SQLite solo lectura (`mode=ro`) y no crea archivos vacíos por errores de ruta.
- Verifica existencia, cabecera SQLite, tablas requeridas, metadatos de versión, tamaño de features y columnas necesarias.
- Devuelve mensajes explicativos para rutas inexistentes, archivos vacíos, .pb ajenos o esquemas incompatibles, antes de comenzar entrenamiento.
- `sargon_train.py` informa versión `0.6.29` al iniciar.

## Alcance
No modifica las fórmulas de entrenamiento, el formato del .pb ni los pesos .npz. Se distribuyen solo `pb_data.py` y `sargon_train.py`.
