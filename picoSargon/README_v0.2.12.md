# picoSargon v0.2.12 — LED sin TCP, recuperación Wi-Fi y telemetría UCI

**Parche incremental sobre v0.2.11** para Raspberry Pi Pico W / Pico 2 W. No cambia búsqueda, Grumpy, Mailbox120, reglas ni evaluación. Copiar `include/config.h`, `src/pico_main.cpp` y `CMakeLists.txt` conservando las rutas.

## Configuración editable en `include/config.h`

- `DEBUG=false`: nunca espera apertura de terminal USB; no imprime información operativa, niveles, nodos ni memoria. Los datos de búsqueda siguen calculándose.
- `DEBUG=true`: espera USB CDC al inicio, luego emite telemetría operativa, memoria y búsqueda.
- `UCI=true`: **solo traza serie** `UCI <<` (recibido por TCP) y `UCI >>` (enviado por TCP), si USB CDC está conectado. Funciona independientemente de DEBUG y **nunca interrumpe ni modifica el protocolo TCP/UCI**.
- `UCI=false`: no imprime trazas UCI. Las respuestas TCP/UCI siempre se envían.
- `MDNS_ENABLED=true`: CMake enlaza `pico_lwip_mdns` y anuncia `<MDNS_HOSTNAME>.local` y el servicio `_uci._tcp` en `PORT`; se conserva la lógica de registro ya presente en v0.2.11. Con `false` no compila mDNS. Resolución `.local` requiere soporte mDNS en el equipo cliente y la red.
- `WIFI_RETRY_MS=10000`: tras detectar pérdida de Wi-Fi espera **10 segundos** antes de un nuevo intento. Repite los intentos de conexión de forma indefinida. También aplica un máximo de 10 segundos a un intento de conexión pendiente y 10 segundos antes de reintentarlo; no bloquea el servicio LED.
- `DEPTH`, `QDEPTH`, `TIMEOUT_MS`, `PORT`, `SSID` y `PASSWORD` se mantienen.

**ATENCIÓN:** `config.h` contiene credenciales locales en texto claro. Antes de sustituirlo, conservar o volver a escribir SSID, PASSWORD, PORT y preferencias actuales. No subir el archivo con contraseñas a repositorios públicos.

## Señal LED (LED integrado CYW43)

Cuando **no hay cliente TCP conectado**, tanto si Wi-Fi está arriba como caído, el patrón es:

- 150 ms encendido, 300 ms apagado
- 150 ms encendido, 300 ms apagado
- 150 ms encendido, 700 ms apagado

Ciclo completo 1750 ms, repetitivo. Los otros estados conservan su cadencia anterior cuando TCP está conectado: búsqueda 3000 ms; listo 1000 ms; error fatal 100 ms. La señal de falta de TCP también acompaña los reintentos Wi-Fi.

## Compilar

Desde la raíz del proyecto picoSargon en VS Code/PowerShell:

```powershell
.\build.ps1 -Board pico_w
# o, para Pico 2 W
.\build.ps1 -Board pico2_w
```

El script exacto del proyecto debe admitir el nombre de placa indicado (verificar opciones de su propia versión). Cuando se cambia `MDNS_ENABLED`, volver a configurar con CMake: la dependencia está atada a `config.h` mediante `CMAKE_CONFIGURE_DEPENDS`.

## Pruebas sugeridas en hardware

1. Arrancar con `DEBUG=false`, `UCI=true` y sin cliente TCP. Verificar la secuencia LED sin USB conectado.
2. Conectar TCP/UCI y enviar `uci`, `isready`, `position startpos`, `go`; verificar `uciok`, `readyok` y `bestmove`.
3. Desconectar el Wi-Fi/AP. El LED debe retomar la secuencia sin TCP, y el firmware debe seguir vivo. Restituir el AP y verificar nuevo enlace (reintentos cada 10 s) y nueva conexión TCP.
4. Conectar monitor USB: `UCI=true` muestra `UCI <<`/`UCI >>`; `UCI=false` los suprime; `DEBUG=false` no muestra estadísticas.
5. Con `DEBUG=true`, el firmware no debe empezar hasta conectar terminal USB. Verificar memoria, nodos y mensajes de funcionamiento.
6. Con `MDNS_ENABLED=true`, probar `picosargon.local` desde un cliente con mDNS activo, incluso después de pérdida y retorno de Wi-Fi.

## Validación y limitaciones

Se verificó la sintaxis y estructura del parche, la secuencia LED mediante prueba lógica y que no se modifican `board.cpp`, `engine.cpp` ni `grumpy.cpp`. **No se compiló `.uf2` ni se probó físicamente en Pico W/2 W en este entorno**, por falta de SDK ARM y placa. La reconexión y mDNS aún requieren validación en hardware.
