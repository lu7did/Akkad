# picoKeras x86 v0.1.2 — build autónomo

`build.ps1` busca TFLM en `third_party/tflm-tree` y `third_party/tflm-build`. Si no encuentra encabezados y biblioteca compilada, ejecuta `scripts/install_TFLM.ps1 -Generator <generador>` y vuelve a buscar los artefactos.

Uso normal: `./build.ps1` (sin argumentos). Se mantienen los argumentos avanzados `-TflmInclude` y `-TflmLibrary`.

**Nota:** la compilación del repositorio TFLM en Visual Studio está condicionada a su compatibilidad efectiva con el toolchain y los operadores ViT. El cambio corrige el fallo inmediato de exigir argumentos manuales; no garantiza que el compilador externo construya todas las dependencias.
