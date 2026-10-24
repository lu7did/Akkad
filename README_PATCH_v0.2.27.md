# picoAlpha v0.2.27 — Contención de memoria MCTS

Parche incremental sobre **v0.2.26**. Conservar archivos no incluidos.

- Árbol segmentado: reserva anticipada por bloques hasta máximo 4096 nodos (o menos si no supera admisión conservadora), antes de simular.
- **Ningún bloque adicional del árbol se asigna durante una simulación**. La saturación sigue la ruta NoMemoryExpansion existente: no propaga ceros como valor neuronal y evita revisitar ramas bloqueadas.
- Si la reserva inicial falla, se captura std::bad_alloc en `run_search` y se intenta emitir una jugada legal de respaldo.
- Durante simulación, `bad_alloc` recibe reason=allocation_error, en lugar de mezclarse con saturación del pool.
- Telemetría MEM_MODE / MEM_POOL para el presupuesto: target, reserved, used, preflight_denied, reserve_bytes, dynamic_growth=0.
- Conserva ON doble núcleo, FC1 INT8 solo núcleo 0, watchdog, PUCT.

## Advertencias verificables

Esta versión elimina *crecimiento dinámico del árbol durante simulaciones*, pero NO elimina todas las asignaciones temporales de tablero/red: `Board::legal`, `encode`, vectores auxiliares y asignaciones del SDK todavía pueden requerir heap. Tampoco constituye prueba de ausencia de PANIC del SDK por agotamiento del heap. Límite 4096 reduce árbol máximo respecto de búsquedas anteriores que alcanzaron ~5888 nodos; puede afectar calidad, debiendo medir `MEM_POOL` y visitas.

Validación: sintaxis C++17 nativa de mcts.cpp. No se realizó compilación firmware ARM ni prueba en Pico 2 W.
