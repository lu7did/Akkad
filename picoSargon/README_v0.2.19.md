# picoSargon v0.2.19 — Estados LED / telemetría

Parche incremental sobre v0.2.18. Solo reemplaza `src/pico_main.cpp`. NO sustituye `include/config.h`, `config/lwipopts.h`, pesos ni scripts.

- Sin Wi-Fi (arranque, caída y reconexión): tres pulsos de 150 ms, pausas de 300 ms, luego 700 ms apagado (ciclo 1750 ms).
- Con Wi-Fi, servidor TCP escuchando o cliente conectado en reposo: LED encendido fijo.
- Mientras el motor busca: LED encendido 2 s y apagado 2 s.
- Error fatal del evaluador: 200 ms encendido y 200 ms apagado. Si falla la inicialización CYW43, el LED Wi-Fi puede no estar operativo.
- `TCP/UCI server ready: listening on port ...` se informa al abrir listener cuando DEBUG=true; `readyok` continúa siendo la respuesta protocolar a `isready`.
- Se eliminan las trazas por cada transición Wi-Fi y de comienzo de conexión exitoso; conservan mensajes de conexión exitosa, caída, timeout y fallo.
- DEBUG=false suprime diagnóstico operativo y no espera serie; UCI=true mantiene traza serie de RX/TX independientemente de DEBUG (cuando USB está conectado).

**No se modifican las reglas ajedrecísticas ni búsqueda.**

Aplicación en raíz del repositorio: descomprimir con reemplazo y ejecutar `./build.ps1`. Compilación física y prueba LED todavía pendientes.
