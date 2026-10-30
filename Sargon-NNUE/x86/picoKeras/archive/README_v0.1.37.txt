picoKeras v0.1.37 EXPERIMENTAL: kernels TFLM adicionales GELU y REDUCE_PROD.
Base: v0.1.36. Parche incremental en sargon-nnue/x86/picoKeras.
GELU: lut 256 elementos calculada en Prepare, Invoke solo consulta enteros.
REDUCE_PROD: reduce enteros INT32, admite ejes positivos/negativos; falla en overflow.
No se ha compilado ni probado en Windows. Requiere fuentes TFLM de la linea base adjunta.
IMPORTANTE: El comando --help del script no demuestra que picoKeras haya ejecutado inferencia.
No se ha verificado que el modelo pueda cargar y ejecutar todas las operaciones.
