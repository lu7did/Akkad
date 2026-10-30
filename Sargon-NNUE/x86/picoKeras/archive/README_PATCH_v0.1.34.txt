picoKeras v0.1.34 - PARCHE INCREMENTAL (requiere v0.1.33)

Objetivo: contrastar conversión TFLite directa del .keras original con la reconstrucción export_graph.py.
No modifica arquitectura, pesos ni kernels C++. No se presume conversión completa.

Desde sargon-nnue/x86/picoKeras:
.\scripts\compare_keras_int8.ps1 -Keras "C:\Users\pedro\github\bobby\akkad\Sargon-NNUE\data\runs\keras\small.keras" -OutputDir ".\diagnostics134"

Se ejecutan dos conversiones con 256 muestras de calibración y 64 de validación, mismas semillas y parámetros.
Se generan modelos FP32, INT8 rechazados si falla, informes individuales y summary JSON.
El exit code 2 significa que al menos una ruta no fue aprobada (resultado experimental, no error en la instalación).

Alternativa: scripts/int8_pipeline.ps1 -Source direct o -Source clone y parámetros habituales.
La conversión directa puede FALLAR si el Keras original utiliza operaciones incompatibles.
No afirmamos haber ejecutado TensorFlow: no está instalado en este entorno.
