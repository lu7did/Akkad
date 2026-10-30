# picoSargon v0.2.23 — tiempo UCI

Añade `time <milisegundos>` al mensaje estándar `info` que sigue a cada búsqueda.
La medición utiliza `std::chrono::steady_clock`, desde inmediatamente antes de
`engine.search()` hasta su retorno. No incluye carga de Grumpy ni inicialización
del proceso. Conserva profundidad, score, nodos, bestmove y STEROIDS.

Ejemplo: `info depth 6 score cp 6 nodes 33578 time 1021`

Aplicar el ZIP en la raíz Akkad; reconstruir picoSargon en cada plataforma.
