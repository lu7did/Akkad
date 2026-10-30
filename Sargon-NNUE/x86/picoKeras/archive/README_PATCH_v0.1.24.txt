picoKeras x86 v0.1.24 - parche incremental sobre v0.1.23

CORRECCIONES
1. Evita consumir una sola vez el generador de muestras: materializa calibracion y reutiliza las mismas muestras en todas las LayerNormalization y en la cuantizacion.
2. Pasa la entrada a cada Keras probe como diccionario con el nombre de la entrada del modelo, evitando la advertencia de estructura que aparecia con input_layer_4.
3. Comprueba el numero de muestras antes de iniciar la conversion.

LIMITACIONES / VERIFICACION
Pruebas realizadas: compilacion Python y prueba aislada con dobles para varias capas de normalizacion; sin TensorFlow instalado no es posible probar conversion .keras/.tflite real aqui. El uso de BatchNorm congelada aproxima LayerNorm, no la reproduce exactamente; la validacion de error frente al TFLite FP32 sigue siendo obligatoria.

Aplicar el zip desde la raiz Akkad, conservando sargon-nnue/x86/picoKeras/. No incluye linea base completa.
