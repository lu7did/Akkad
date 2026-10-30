picoKeras v0.1.45 - 4 scripts de una sola orden cada uno.
Los argumentos estan escritos directamente en cada script: editar sus valores dentro del archivo.
keras_download.ps1: reemplazar la URL example por una URL real antes de ejecutar.
Ejecutar desde sargon-nnue/x86/picoKeras. No hay variables propias, param, comprobaciones, ni orquestacion en .ps1.
keras_tflite.py usa --keras --output. keras_int8_convert.py usa --tflite.
La conversion INT8 sigue dependiendo del .keras original mediante el .source.json generado por keras_fp32_export.py.
El modelo funcional de v0.1.42 esta congelado en batch=1. No se ha validado esta entrega en Windows.
