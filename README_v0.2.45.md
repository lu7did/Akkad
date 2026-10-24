# picoAlpha v0.2.45 — corrección inicio de partida en ply 1

Parche incremental sobre v0.2.44. Sustituye únicamente `picoAlpha/tools/picoDistiller/common.py`.

## Error corregido
`reconstruct_game()` rechazaba partidas cuyo primer registro muestreado es `ply=1`, aunque la posición inicial implícita de ajedrez permite reconstruir la primera jugada. Ahora acepta `ply=0` y `ply=1`, valida la transición legal única desde `chess.Board()` y conserva el `move_stack` completo para consultas LC0 con historial real. Las partidas con saltos de ply o transiciones imposibles continúan produciendo un error explícito.

## Ejecutar
Reutilice `run_prepare.ps1` sin cambios. Las evaluaciones ya escritas permanecen en la tabla `pico_distillation`; una nueva ejecución las sobrescribe.

## Validación
`python -m py_compile` correcto. Prueba real con `.pb` y lc0-bindings de Windows pendiente.
