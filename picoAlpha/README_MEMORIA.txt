picoAlpha v0.2.12 — PARCHE INCREMENTAL ACUMULATIVO: UCI nodes + instrumentacion de heap

Requiere la linea de base original picoAlpha.zip, con el primer parche de diagnostico MCTS incorporado. Este ZIP incluye los tres archivos resultantes, de forma que reemplaza la correccion UCI anterior y las modificaciones de diagnostico MCTS.

Archivos: include/mcts.hpp, src/mcts.cpp, src/pico_main.cpp. No modifica configuracion, secretos Wi-Fi, TinyGyal ni parametros de busqueda.

Mediciones en monitor serie, por jugada:
 MEM heap_before_used / heap_before_free_blocks / heap_before_arena
     heap_peak_used / heap_min_free_blocks / heap_peak_arena
     heap_after_used / heap_after_free_blocks / heap_after_arena
     node_size / tree_bytes

UCI transmite info nodes <tree_nodes>; info string mcts ... se mantiene.

IMPORTANTE: mallinfo() (newlib) mide estadisticas del heap del asignador, NO la RAM libre fisica total. fordblks son bloques libres DENTRO del arena del heap, no SRAM adicional disponible. Los picos estan muestreados al final de cada simulacion; pueden subestimar picos transitorios dentro de una evaluacion. La diferencia before/after incluye el hecho de que el arbol se destruye al terminar search(). No usar estas cifras solas para activar un HWM.

Ejecutar benchmark habitual, conservando monitor serie completo. Construccion y prueba fisica NO realizadas en este entorno.
