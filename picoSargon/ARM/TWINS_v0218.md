# TWINS v0.2.18 — instrumentación y seguridad

Parche incremental relativo a `akkad/`. Aplicar sobre TWINS v0.2.17.

- `TWINS compiled ON` indica compilación; `core1_ready=1` confirma arranque del worker.
- El arranque espera hasta 2 segundos por la confirmación, alimentando el watchdog. Si el worker no responde, registra `TWINS FATAL` y rechaza búsquedas TWINS sin fingir trabajo paralelo.
- Por profundidad: movimientos por núcleo, nodos y milisegundos por núcleo, espera en barrera, actualizaciones de alfa, scouts y podas atribuibles al umbral compartido.
- `alpha_prunes` son scouts que no superaron el umbral leído, NO una medición contrafáctica de nodos realmente ahorrados por la cooperación. `alpha_updates` son publicaciones exitosas de valores verificados.
- Cualquier resultado incompleto continúa provocando que se descarte esa profundidad.
- Con TWINS desactivado, los bloques añadidos no se compilan y la búsqueda estándar permanece igual.
- No se verificó en hardware: revisar ocupación SRAM/stack, compilación SDK y funcionamiento multicore antes de desplegar en competición.
