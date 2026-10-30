picoKeras v0.1.22 - conversores consistentes

Ambos conversores comparten tools/export_graph.py, que adapta mixed_float16 a FP32 y GELU exacta a tanh. El INT8 ya no convierte nuevamente el grafo Keras original incompatible.

Desde picoKeras:
  .\scripts\keras_to_tflite.ps1 -In .\models\small.keras -Out .\models\small.tflite
  .\scripts\tflite_to_int8.ps1 -In .\models\small.tflite -Out .\models\small.int8.tflite

Si INT8 falla por operadores o tensores float, no genera el archivo final. La compatibilidad TFLM no esta garantizada y debe verificarse por separado.
