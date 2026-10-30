Experimento v0.1.29: LayerNormalization 71, cuantización de entrada.
Depende del archivo tools/probe_layernorm_int8.py entregado en v0.1.27.
No modifica ni sustituye los conversores.
Desde sargon-nnue/x86/picoKeras:
.\scripts\probe_layernorm_71_scales.ps1 -Keras 'C:\Users\pedro\github\bobby\akkad\Sargon-NNUE\data\runs\keras\small.keras' -CalibrationSamples 64 -ValidationSamples 64 -MaxError 0.20 -Report '.\layernorm_71_scales_v0.1.29.json'
Compara escala estatica global, escala estatica por canal (ingreso solamente), escala dinamica por fila.
La salida se escala exclusivamente con calibración, sin fuga de validación.
Un error mayor al umbral no es fallo de ejecución; queda indicado por pass_by_strategy en el JSON.
No produce un modelo TFLite ni demuestra implementacion TFLM.
