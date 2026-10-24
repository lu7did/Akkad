# picoAlpha v0.2.51 — telemetría básica

Parche incremental sobre v0.2.50. Solo `src/pico_main.cpp` y `CMakeLists.txt`.

Por defecto, la consola mantiene banner, red compilada, estado de conexión, inicio/fin de búsqueda, resumen SEARCH (simulaciones, motivo, ms, nodos, Q), errores y UCI. Los diagnósticos `MCTS`, `NN` y `MEM` están desactivados.

Para habilitar diagnóstico, configurar CMake con `-DPA_TELEM_DETAIL=ON` y los grupos deseados `-DPA_TELEM_MCTS=ON`, `-DPA_TELEM_NN=ON`, `-DPA_TELEM_MEM=ON`. Se necesita reconfigurar y recompilar. El interruptor maestro también evita que antiguos valores cacheados ON activen el diagnóstico accidentalmente.

No se modifica el modelo, los pesos, UCI, búsqueda ni hardware.
