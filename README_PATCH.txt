picoAlpha incremental patch sobre la entrega anterior v0.2.12 UCI + memoria.
Reemplazar: include/mcts.hpp, src/mcts.cpp, src/pico_main.cpp.
No cambia Sargon-NNUE ni picoSargon ni config.h.

MCTS: 1600 es reserva inicial. Crecimiento +512 nodos, con un guard
mínimo de 48 KiB entre heap brk y stack actual, y límite de utilización
de 90% del margen residual. Se comprueba la memoria transitoria durante
std::vector::reserve (buffer nuevo más anterior). Fallo de crecimiento =>
reason=memory_limit y mejor jugada conocida.

Telemetría agrega growth_events, conserva tree_nodes, tree_capacity,
memoria mallinfo y formato UCI info nodes.

IMPORTANTE: esta no es una medición global exacta de memoria libre;
stack-heap gap es una salvaguarda conservadora del proceso en ejecución.
Validar que sbrk(0) y el linker RP2350 presenten direcciones coherentes.
No está compilado ni probado en la Pico 2 W en este entorno.

La ruta de inferencia NN (net.cpp) domina aproximadamente 0.2 s por
simulación; no se cambia numéricamente sin prueba comparativa contra LC0.
La optimización implementada consiste en no terminar búsquedas por la
capacidad fija: seguir hasta tiempo/simulaciones/memoria.
