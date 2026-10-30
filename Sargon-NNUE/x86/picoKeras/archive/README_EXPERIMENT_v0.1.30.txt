picoKeras v0.1.30 - parche correctivo incremental del experimento v0.1.29

Correccion: affine_params() devuelve tensores con keepdims=True; convertir s/z
con float(s) o int(z) falla para arrays multidimensionales (NumPy actual).
Ahora se usa .item() exclusivamente en la variante static_tensor.
Las otras dos variantes conservan sus escalas en arrays.
Incluye prueba de regresion para las tres ramas sin TensorFlow.

Aplicar desde la raiz de Akkad, preservando sargon-nnue/x86/picoKeras/.

Prueba previa (en ambiente con numpy):
  cd sargon-nnue/x86/picoKeras/tools
  python test_probe_layernorm_71_scales.py

Experimento (desde picoKeras):
  .\scripts\probe_layernorm_71_scales.ps1 -Keras "C:\Users\pedro\github\bobby\akkad\Sargon-NNUE\data\runs\keras\small.keras" -CalibrationSamples 64 -ValidationSamples 64 -MaxError 0.20 -Report ".\layernorm_71_scales_v0.1.30.json"

No se genera TFLite INT8. No se ha ejecutado aqui contra el modelo .keras usando TensorFlow.
No sustituye la validacion de la arquitectura completa ni de TFLite Micro.
