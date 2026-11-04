# picoKeras/ARM v0.1.26 — corrección de ruta del port TFLM

Aplicar desde la raíz de Akkad encima de v0.1.25.

Corrige en `cmake/tflm.cmake` la resolución de `src/tflm_pico_port.cpp`: el directorio de `CMAKE_CURRENT_LIST_DIR` es `picoKeras/ARM/cmake`, no `picoKeras/ARM`. Se añade comprobación explícita de existencia.

Se incrementa la versión en build.ps1, CMakeLists.txt y en la identificación y banner UCI. No cambia la implementación de TFLM.

Comando: `cd picoKeras/ARM; ./build.ps1 -Clean`.

No se verificó compilación cruzada en Windows; podrían surgir errores adicionales después de esta fase de configuración.
