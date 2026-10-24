# picoAlpha v0.2.28 — estabilización de memoria desde v0.2.27

- Doble núcleo desactivado **forzadamente** por CMake (PA_DUAL_CORE_NN=OFF), evitando un caché CMake con ON heredado. Para volver a probarlo se requiere cambiar explícitamente la configuración de esta versión.
- Árbol MCTS en **arena SRAM estática**, 6144 nodos x 28 bytes = 172032 bytes de BSS. Se elimina la asignación dinámica de bloques de nodos antes y durante cada búsqueda y las tablas de punteros de bloques.
- Si la arena se llena, se rechaza solo la expansión y se conserva backup válido, sin incrementar estadísticas con valores ficticios. A diferencia de v0.2.27 no se impone el techo arbitrario de 4096.
- Workspace neuronal **persistente** entre búsquedas: los vectores mantienen su capacidad después de la primera búsqueda; deja de liberarse y reconstruirse el scratch 128 veces por partida. Se mantiene búsqueda secuencial única.
- Diagnóstico MEM_MODE y MEM_ARENA confirma memoria de nodos estática, usada, y cero asignación dinámica para el árbol.
- La reserva SRAM estática reduce el margen de RAM disponible para otros módulos: comprobar tamaño de .bss/elf durante build ARM. No se ha ejecutado hardware.

Validar específicamente el compilado ARM y el tamaño de SRAM con `arm-none-eabi-size <ruta-a-picoAlpha.elf>`. Comparar ejecución de 128 simulaciones y estabilidad a lo largo de 40 búsquedas. La red y sus pesos no cambian.
