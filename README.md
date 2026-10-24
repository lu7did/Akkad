# picoAlpha v0.2.41 — parche incremental sobre v0.2.40

Archivos modificados: `picoAlpha/src/mcts.cpp` y `picoAlpha/CMakeLists.txt`.

## Cambios
- Expansión progresiva: los nodos reservan inicialmente hasta cuatro hijos con mayor prioridad P, en vez de reservar todos los movimientos legales. Los hijos adicionales se materializan tras suficientes visitas (umbral: ocho visitas por hijo existente). Cuando necesita ampliar, se vuelve a calcular P para identificar la mejor alternativa legal que aún no tiene nodo. No se eliminan definitivamente movimientos legales.
- Hijos enlazados dentro de la misma arena; Node sigue midiendo 20 bytes y el límite continúa en 8.576 nodos. Ambos perfiles NN conservan su selección actual, sin modificaciones a los evaluadores o pesos.
- Fin inmediato con `reason=tree_full` si no puede crearse otro nodo, en lugar de cientos de iteraciones abortadas y `reason=complete`.
- Versión 0.2.41 en CMake, que alimenta el encabezado generado para el banner.

## Pruebas realizadas en PC
- Compilación y ejecución de `src/board.cpp`, `src/net_1x8.cpp`, `src/mcts.cpp` con g++: 1200 simulaciones, 5054/8576 nodos, reason=complete, aborted=0 desde la posición inicial.
- Ejecución con presupuesto de 5000: 2031 simulaciones, 8576/8576 nodos, reason=tree_full, aborted=1. (Ensayo anterior al pequeño ajuste final de preservación del motivo de terminación.)

No se ha compilado con el SDK de Raspberry Pi ni probado físicamente. El aumento de inferencias causado por el ensanchamiento progresivo puede afectar el tiempo total: comprobar en la placa.

## Aplicación
Extraer este ZIP en el directorio padre de picoAlpha (Akkad), conservando la estructura `picoAlpha/...`; luego, desde picoAlpha, ejecutar `./build.ps1`.
