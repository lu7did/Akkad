# picoAlpha — ajuste mínimo de política de memoria (v0.2.14, parche incremental)

## Base
Aplicar sobre picoAlpha con las revisiones de MCTS dinámico, instrumentación MEM y finales/watchdog (parche coordinado Sargon-NNUE v0.6.169).

## Cambios
Solo `picoAlpha/src/mcts.cpp`: antes de usar el cálculo conservador sbrk(0)-stack, permite intentar reservar un bloque nuevo si mallinfo().fordblks (bloques libres del heap) cubre el bloque completo más 16 KiB de margen. La ampliación continúa usando `std::vector::reserve()` y maneja `std::bad_alloc`; si no hay margen en el heap existente, conserva el guardarraíl anterior de 48 KiB y 90% para extender el heap.

No cambia red, MCTS/PUCT, historial, límites de simulación/tiempo, firmware picoSargon, ni Sargon-NNUE. La variable `max_nodes=1600` sigue indicando capacidad inicial.

## Riesgos y validación
`fordblks` es memoria libre agregada y no garantiza un bloque contiguo; `reserve` puede fallar. La comprobación heap-pila basada en `sbrk` sigue siendo aproximada; la seguridad con Wi-Fi y USB requiere prueba física. Compilar sobre el SDK del usuario y repetir misma FEN/timeout. Verificar `growth_events`, `reason`, `heap_peak_arena`, `heap_min_free_blocks`, reinicios y conectividad. No aumentar límites todavía.

## Comparación esperada
Especialmente SEARCH_ID 40–42: con `heap_before_free_blocks` ~200 KiB, debería poder al menos intentar una expansión a 2112; si falla, el asignador, no el filtro artificial, habrá rechazado la asignación.
