# picoAlpha v0.2.23 — Watchdog dentro de kernels y diagnóstico persistente

Parche incremental sobre v0.2.22. Archivos: `include/net.hpp`, `include/mcts.hpp`, `src/net.cpp`, `src/mcts.cpp`, `src/pico_main.cpp`, `CMakeLists.txt`.

- Callback de progreso durante convoluciones (cada cuatro casillas), FC INT8 (cada ocho filas), FC FP32 y política selectiva. Alimenta watchdog solo con avance verificable y aborta por deadline.
- Marcadores de fase en scratch[0..3] del watchdog. En el siguiente arranque tras reinicio muestra `WD_LAST search= phase= step=`.
- Instrumentación de fases MCTS para legalidad, reserva, inferencia, push y backup.
- Mantiene el MCTS segmentado, INT8, deadline y guardas previas.
- Si el procesamiento se atasca dentro de una operación que no invoca el hook, el watchdog reinicia y muestra la última fase conocida.

El control de deadline puede producir `exception_inner` en la búsqueda; conservamos la mejor jugada disponible.

No realizado: compilación ARM Pico SDK o prueba en hardware.
