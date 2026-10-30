picoKeras v0.1.23 — FrozenNorm para INT8

PARCHE INCREMENTAL. Instalar desde la raíz del repositorio Akkad.
Los archivos del ZIP comienzan con sargon-nnue/x86/picoKeras/.

El conversor reconstruye el modelo a partir del archivo .keras registrado
por el .tflite.source.json; no puede cuantizar un TFLite arbitrario.

Cambio: cuando la arquitectura contiene LayerNormalization(axis=-1), estima
media/varianza por canal con las posiciones de calibración y la sustituye
por BatchNormalization congelada (operación afín cuantizable).

ADVERTENCIA TÉCNICA IMPORTANTE:
La normalización congelada NO equivale matemáticamente a LayerNormalization.
Puede deteriorar significativamente la precisión, particularmente con
activaciones no estacionarias. Por eso la comparación de inferencia contra
el modelo FP32 original sigue siendo obligatoria; si el error máximo supera
el umbral, no se guarda ningún .int8.tflite. Esto NO garantiza equivalencia
en todas las posiciones ni compatibilidad completa con un runtime TFLM dado.

Ejecución (PowerShell, desde picoKeras):
  .\scripts\tflite_to_int8.ps1 -In '.\models\small.tflite' -Out '.\models\small.int8.tflite' -Verbose

Se necesitan las dependencias Python ya instaladas: tensorflow, keras,
numpy y python-chess. Se requiere el .keras original y el manifest .source.json.
Opciones CLI Python: --calibration-samples (default 256),
--validation-samples (default 16), --max-error (default 0.20).

Verificación realizada: compilación sintáctica Python (py_compile).
No se ejecutó una prueba de inferencia/convertidor real; requiere disponer
localmente de las redes, de TensorFlow y sus dependencias en Windows.
