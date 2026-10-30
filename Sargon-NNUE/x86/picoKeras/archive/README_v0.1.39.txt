picoKeras v0.1.39 — correccion del enlazado de GATHER INT32.

Causa comprobada: CMakeLists.txt enlaza TFLM_LIBRARY apuntando a la biblioteca ya construida
third_party/tflm-build/lib/Release/tflm.lib. Compilar solo picoKeras NO recompila gather.cc.

Aplicar SOBRE v0.1.38, extrayendo este ZIP desde la raiz Akkad.

Desde sargon-nnue/x86/picoKeras:
  .\scripts\rebuild_tflm_and_try.ps1 -Network '.\small.mul.int8.tflite'

Reconstruye primero la biblioteca tflm, comprueba que CMake usa esa biblioteca y
recompila picoKeras; luego prueba UCI. No vuelve a cuantizar el modelo.

No asegura que la siguiente operacion TFLM sea compatible: solo resuelve que
el parche a gather.cc no llegaba al ejecutable. No probado en MSVC remoto.
