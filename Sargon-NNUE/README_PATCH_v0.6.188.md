# Sargon-NNUE v0.6.188 — Keras INT8: clone_model / keras.ops.Add

Parche incremental. Extraer desde la raiz Akkad/. Requiere parches anteriores hasta v0.6.187.

## Correccion
`keras.models.clone_model()` aplica clone_function tambien a operaciones simbólicas `keras.ops` (ej. `Add`), cuyo constructor `Operation.__init__` no acepta `dtype`. La v0.6.187 agregaba `dtype='float32'` a todos los objetos y producia TypeError antes de cuantizar.

Ahora se establece `dtype='float32'` solamente en objetos que son instancias `keras.layers.Layer`; las operaciones simbólicas mantienen su configuración serializada original.

## Verificacion realizada
Con backend Keras NumPy (sin TensorFlow) se construyó una red funcional Dense(float16) -> keras.ops.add -> Dense(float16); se verificó clonación FP32, copia de pesos, semejanza de salidas, quantize('int8') y presencia de dos kernels INT8. Sintaxis Python y ZIP verificados.

No se probó la arquitectura completa ViT-Small ni la exportación TF SavedModel debido a falta de TensorFlow y modelo .keras en este entorno.

Uso: volver a ejecutar `./run_keras_INT8.ps1`.
