# Nurse TRAIN — corrección visual v0.1.52

Parche incremental sobre v0.1.51. Cambia únicamente la presentación de `SelectionProgress` en `nurse/train/train.py`:

- `PARTIDAS DB` y `POSICIONES DB` usan `█` y `░`, como las barras TRAIN/VALIDATION.
- Porcentaje con dos decimales.
- Se conservan la actualización en la misma línea, control de ancho de consola, finalización única y salida redirigida.
- No se modifican selección, entrenamiento, NPZ, rutas ni scripts PowerShell.

El carácter visual se escribe como UTF-8, al igual que la telemetría de entrenamiento. En PowerShell, utilizar terminal compatible con UTF-8.
