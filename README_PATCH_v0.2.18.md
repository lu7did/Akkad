# picoAlpha v0.2.18 — Árbol segmentado ACTIVADO por defecto

Este parche incremental se aplica **después de v0.2.17**. Reemplaza solamente `picoAlpha/CMakeLists.txt`; conserva intactos el MCTS segmentado de v0.2.17 y el historial compacto de v0.2.16.

## Activación normal (predeterminada)
La opción CMake `PA_SEGMENTED_TREE` es `ON` por defecto. El compilador recibe explícitamente `PA_SEGMENTED_TREE=1`. Durante la configuración se imprime `picoAlpha segmented MCTS tree: ON`.

## Desactivación o reversión
En la configuración CMake utilizar `-DPA_SEGMENTED_TREE=OFF` y recompilar; se transmite `PA_SEGMENTED_TREE=0` y queda activo el árbol monolítico anterior. Para reactivar, ejecutar con `-DPA_SEGMENTED_TREE=ON` o eliminar una caché de configuración que guardase OFF y volver a configurar.

IMPORTANTE: CMake guarda las opciones de `-D` en `CMakeCache.txt`. Una selección previa OFF seguirá siendo OFF aunque el valor por defecto sea ON, hasta que se cambie explícitamente. Consultar la línea `picoAlpha segmented MCTS tree: ...` para confirmar.

No hay cambios en parámetros de búsqueda, red ni mecanismo de protección de memoria. No se ha verificado la compilación para ARM ni en hardware.
