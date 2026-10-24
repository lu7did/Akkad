# picoAlpha v0.2.15 — reversión segura del guardarraíl v0.2.14 + diagnóstico

Parche incremental sobre picoAlpha con historial UCI, watchdog y telemetría previos (v0.2.14). No aplicar a picoSargon. No reemplazar otros archivos del firmware.

Archivos: src/mcts.cpp, include/mcts.hpp, src/pico_main.cpp.

- Revierte exclusivamente la rama de `has_growth_room()` que aprobaba una realocación a partir de `mallinfo().fordblks` agregado. Conserva reserva de 48 KiB y 90 % del margen estimado heap-pila de la política anterior.
- Agrega `MEM_GROW` por búsqueda: intentos, ampliaciones, rechazos por guardarraíl, fallos `bad_alloc`, capacidades y bytes solicitados.
- Agrega `board_size` y `history_entries` para cuantificar la huella de historial antes de cambiar su representación.
- No cambia MCTS, red, parámetros de búsqueda, transmisión de jugadas, watchdog ni LEDs.

Validación: compilar con build.ps1 y placa pico2_w. Ejecutar primero 2 partidas y comprobar `MEM_GROW`, `heap_before_used`, `heap_after_used` y ausencia de PANIC. No reanudar torneos largos hasta verificar estabilidad.

No se realizó compilación ARM/Pico SDK ni validación física aquí. Nota: el guardarraíl basado en stack local es heurístico; la solución estructural a futuro es almacenamiento MCTS segmentado.
