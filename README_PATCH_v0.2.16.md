# picoAlpha v0.2.16 — historial compacto reversible

**Solo picoAlpha**. Aplicar sobre la linea de base v0.2.15. Sobrescribir los 6 archivos bajo picoAlpha/ que aparecen en este ZIP. Conservar backups de estos archivos.

## Cambio
- Representación activa `Board` sin modificar; `Board::push/pop`, legalidad, historial interno de repeticiones, red y MCTS siguen iguales.
- Historial de posiciones para inferencia pasa de `std::vector<Board>` a `std::vector<CompactState>`: 32 bytes de casillas empaquetadas, turno, enroques, halfmove y flag de repetición. El flag se calcula en el momento de construir el snapshot, preservando los planos de `encode()`.
- Evita además copiar los vectores internos de cada `Board` en cada trayectoria MCTS.
- Fuente delimitada con `PA_COMPACT_HISTORY_BEGIN/END`.

## Reversión INMEDIATA sin cambiar archivos
Agregar a CMake `target_compile_definitions(picoAlpha PRIVATE PA_COMPACT_HISTORY=0)` y recompilar. La función `encode(vector<Board>)` original sigue disponible, y se conserva la ruta anterior en `mcts.cpp`.

## Telemetría
`MEM_HISTORY compact=1 entries=... element_size=... capacity=... reserved_bytes=... active_board_size=...`, y `MEM_GROW ... history_element=... history_bytes=...`.

## Limitaciones
No compacta el historial interno de posiciones del `Board` activo (que es necesario para repeticiones). No cambia el asignador del árbol MCTS ni la política de protección v0.2.15. No hay validación en placa.
