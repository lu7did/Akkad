# picoSargon ARM v0.2.51 — bloqueo durante `go`

Base autorizada: `akkad(20261124-175149).zip`. El firmware standalone de la base
anuncia v0.2.49 aunque config.h indica v0.2.50. Este parche anuncia v0.2.51 en el
firmware standalone y actualiza CMake. No reemplaza config.h, ni los pesos, ni los
argumentos del motor ni los archivos de otros proyectos.

## Defectos observados en el código

- La barrera TWINS esperaba indefinidamente al core 1 incluso tras expirar
  TIMEOUT_MS o recibir stop. El core 0 mantenía vivo el watchdog en la espera.
- Ambos motores reservaban los buffers de los 56 frames en la primera búsqueda,
  independientemente de la profundidad realmente alcanzada.
- Una excepción de core 0 después de publicar el trabajo podía abandonar el
  buzón mientras core 1 todavía lo utilizaba.

No se ha reproducido el bloqueo en el microcontrolador; no se puede afirmar que
alguno de estos defectos sea la causa exclusiva del incidente observado.

## Correcciones

- Reserva de buffers recursivos por demanda, con reutilización entre búsquedas.
- Preparar ambos tableros antes de publicar el trabajo. Si core 0 lanza una
  excepción, pedir stop y esperar a core 1 antes de volver a utilizar el buzón.
- Si vence el plazo de búsqueda o se solicita stop, quit o desconexión, o si
  ocurre una excepción en core 0, esperar como máximo otros 1000 ms en la
  barrera. Si core 1 no termina, emitir diagnóstico y, si es posible, devolver
  la mejor jugada de la última profundidad completa (0000 si no existe), dar
  100 ms a la comunicación y reiniciar mediante watchdog. La entrega TCP del
  mensaje antes de un reinicio no está garantizada.
- Tras reinicio del watchdog, no esperar indefinidamente una consola USB ausente.
- `info string SEARCH begin` y telemetría serie de dispatch y cancelación.
- Reportar error si core 1 devuelve worker-exception.

El algoritmo de evaluación, NNUE, poda y partición de movimientos no cambia.
Se mantiene el límite de búsqueda fijo TIMEOUT_MS de config.h, incluso para
`go wtime ...`; este parche no implementa el control dinámico de reloj UCI.
La espera acotada corresponde a la barrera del core 1; no es una garantía de
recuperación de cualquier bloqueo posible en el hardware o el core 0.

## Validación

Compilación de host Linux, TWINS ON y OFF. PERFT 1/2/3 (20/400/8902) y UCI de host
correctos en ambos casos. Prueba CTest twins_recovery: dos hilos concurrentes,
5 reservas iniciales por motor a profundidad 1, cancelación, deadline, tablero
restaurado y reutilización de buffers correctos. Esta prueba no reproduce la
barrera del firmware ni el SDK/lwIP ni el watchdog del microcontrolador.
No se dispone de toolchain ARM/Pico SDK ni de placa física en este entorno.

## Instalación

Extraer el ZIP sobre la raíz del repositorio Akkad. Recompilar picoSargon ARM
con el build.ps1 y la placa habituales y cargar el nuevo UF2. Comprobar que la
respuesta a `uci` anuncia `picoSargon v0.2.51`. No cambiar la configuración de
PLL, WiFi o red neuronal. La prueba de aceptación es `position startpos` y
`go wtime 300000 btime 300000 winc 0 binc 0` sobre TCP, con la consola serie
conectada para obtener los mensajes de diagnóstico. Si falla, conservar el log
serie desde BOOT y, como prueba aislada, considerar PLL_SYS=0 (reloj SDK).
