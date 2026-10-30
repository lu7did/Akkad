# picoKeras Debian ARM64 — TensorFlow Lite

El código C++ común (main.cpp, board.cpp y sus cabeceras) se toma de `picoKeras/x86/picoKeras/`. No se modifican los archivos del placeholder `picoKeras/ARM/`. Solo el evaluador cambia: `debian/model_tflite.cpp` utiliza la biblioteca C++ de TensorFlow Lite en lugar de TensorFlow C.

## Preparación de las redes
Convertir previamente la red `.tf` a `.tflite` usando el proceso de exportación TensorFlow disponible en la máquina de entrenamiento. La salida debe ser un archivo FlatBuffer `.tflite` que el motor recibe mediante `--network`; no se admite `.tf` en Debian. El modelo debe tener entrada `[N,768]` o `[N,8,8,12]` y una salida escalar por posición, desde el punto de vista del bando que mueve, con rango `[-1, 1]`. Admitidos FLOAT32, INT8 y UINT8; no se garantiza compatibilidad de todos los operadores convertidos. La exportación/cuanti­zación debe verificarse con un conjunto de posiciones de referencia antes de comparar resultados.

## Compilación

En Raspberry Pi OS/Debian ARM64: `BUILD_JOBS=1 bash picoKeras/tools/bash/build.sh`. El script puede instalar paquetes con apt (`INSTALL_DEPS=1`, por defecto), clona TensorFlow v2.18.1 en `picoKeras/debian/third_party/tensorflow` y construye `picoKeras/debian/build/picoKeras`. Cambiar `TF_VERSION` solo con conocimiento de la compatibilidad del código. El proceso requiere conexión y puede consumir bastante memoria, disco y tiempo.

## Prueba

`bash picoKeras/tools/bash/uci_smoke.sh /ruta/modelo.tflite`

`bash picoKeras/tools/bash/run.sh /ruta/modelo.tflite --stdio`

El smoke comprueba `uciok`, `readyok` y `bestmove`. Los datos no garantizan equivalencia numérica frente a TensorFlow C: es necesaria validación con posiciones/outputs conocidos. Esta entrega no está compilada ni probada sobre Raspberry Pi real.
