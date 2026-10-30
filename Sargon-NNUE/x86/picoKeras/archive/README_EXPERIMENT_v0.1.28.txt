picoKeras 0.1.28 - experimento incremental LayerNorm 71
Requiere aplicado previamente parche v0.1.27, porque importa rutinas de tools/probe_layernorm_int8.py.
Desde sargon-nnue/x86/picoKeras ejecutar:
.\scripts\probe_layernorm_71.ps1 -Keras "C:\Users\pedro\github\bobby\akkad\Sargon-NNUE\data\runs\keras\small.keras" -CalibrationSamples 64 -ValidationSamples 64 -MaxError 0.20 -Report ".\layernorm_71_v0.1.28.json"
Compara cuantizacion simetrica/asimetrica, percentiles de rango, saturacion y descompone error de entrada vs aritmetica + cuantizacion de salida.
Solo diagnostico: NO genera FlatBuffer ni implementa kernel TFLM. El resultado FAIL (exit 2) no es una excepción del programa.
IMPORTANTE: escala de salida derivada de validación constituye una estimación OPTIMISTA; no puede usarse para medir la calidad en producción.
