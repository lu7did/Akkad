picoKeras v0.1.32 - pipeline integral experimental (incremental)

Ejecutar desde sargon-nnue/x86/picoKeras:
.\scripts\int8_pipeline.ps1 -Mode convert -Keras "C:\Users\pedro\github\bobby\akkad\Sargon-NNUE\data\runs\keras\small.keras" -Fp32 ".\small.fp32.tflite" -Int8 ".\small.int8.tflite" -Report ".\int8_pipeline_v0.1.32.json"

Modos: convert (export + cuantizar + auditar + validar), audit (auditar existentes), validate (auditar + comparación de salida).
No escribe un .int8.tflite en convert si falla alguna puerta. Siempre escribe JSON de diagnóstico.
Se conserva export_graph.py de la línea de base, sin FrozenNorm.
La comprobación de resolución C++ es inventario de registro únicamente, no prueba de soporte de tipos ni rendimiento.
ATENCION: calibración incluye posiciones legales generadas aleatoriamente, no posiciones reales de entrenamiento. La precisión final en producción requiere calibración representativa.
Limitación: no se ha ejecutado conversión TensorFlow en este entorno. Se han ejecutado pruebas de lógica del pipeline sin TensorFlow.
