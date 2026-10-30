# picoKeras — división de plataformas (etapa preparatoria)

Arquitectura objetivo:

    Akkad/picoKeras/
      x86/picoKeras/     # Motor UCI/TCP + backend TensorFlow (pendiente)
      ARM/               # Pico 2 W + TFLM (pendiente)
      tools/tflite_to_header.py

El conversor incluido es funcional y no requiere TensorFlow para encapsular
un FlatBuffer TFLite; la opción `--require-int8` sí verifica los tensores con
TensorFlow/tflite_runtime. La extensión `.int8.tflite` por sí sola NO demuestra
que todos los operadores estén cuantizados ni que TFLM los soporte.

Este ZIP NO mueve ni sustituye todavía los proyectos existentes; evita romper
brains.json (`../x86/picoKeras/build/Release/picoKeras.exe`) durante la migración.
No incluye firmware funcional ARM, ni backend TensorFlow C++ aún.

Cuando se complete la migración habrá que actualizar rutas de brains.json,
CMake/build.ps1 e integración Sargon-NNUE en un mismo parche de transición.

El runtime TensorFlow completo no se ejecutará en Pico 2 W: allí seguirá TFLM.
Para `.keras`, TensorFlow C API puro no ofrece un cargador Keras equivalente a
`tf.keras.models.load_model`. Hay que definir exportación a SavedModel con
firmas estables, o usar un runtime Python persistente en Windows.
