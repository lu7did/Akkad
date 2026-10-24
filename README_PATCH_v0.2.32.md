# picoAlpha v0.2.32 — identificación UCI y coherencia de configuración

Aplicar sobre picoAlpha v0.2.31 conservando los restantes archivos.

Archivos modificados: `picoAlpha/src/pico_main.cpp`.

- `id author Dr. Pedro E. Colla` (corrección solicitada).
- Nombre UCI, banner de arranque y etiqueta BUILD unificados en v0.2.32.
- La línea MCTS distingue `requested_max_nodes=1600` (configuración histórica) de `effective_tree_capacity=6144` (arena estática real). No se cambia ningún presupuesto ni algoritmo.

No modifica la distribución de memoria, número de simulaciones, pesos de red, velocidad de CPU o núcleos activos.

Verificación estática: reemplazos inspeccionados, ZIP comprobado. Compilación ARM no ejecutada por no disponer del Pico SDK en este ambiente.
