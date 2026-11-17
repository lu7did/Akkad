# Nurse train — progreso de selección (v0.1.49)

Corrección incremental sobre v0.1.48. Solo modifica `nurse/train/train.py`.

Durante la selección se informa de inmediato el inicio y conteo de partidas; se visualiza el progreso de lectura de IDs, el total de partidas seleccionadas y la partición en entrenamiento/validación. A continuación se informa el conteo de posiciones etiquetadas y la lectura progresiva de todas las posiciones (incluidas las que no pertenecen a la muestra). Al finalizar se resumen posiciones inspeccionadas, elegidas, usadas y excluidas.

La barra se actualiza cada ~0,5 segundos como máximo, en la misma línea si stdout es una terminal, o con líneas espaciadas en registros/redirección. No se ha alterado el método de muestreo, las etiquetas, la arquitectura, la partición, el entrenamiento ni las rutas del orquestador.

**Limitación:** `COUNT(*)` en SQLite y la apertura de la base no exponen progreso porcentual interno; se anuncia el inicio de la operación para distinguir demora de falta de ejecución. En bases muy grandes las muestras siguen almacenándose en RAM como antes.
