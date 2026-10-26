# picoSargon v0.2.16 — STEROIDS

Parche incremental con raíz **picoSargon/** para extraer desde `Akkad/`.

`STEROIDS` agrupa **Aspiration Windows**, **SEE** de recapturas legales acotadas y **Razoring** con comprobación por quiescencia. No cambia pesos Grumpy, tablero, protocolos UCI ni configuraciones normales. **Default OFF**. Las fuentes exclusivas están bajo `#ifdef PICOSARGON_STEROIDS`; con OFF se conserva la ruta de búsqueda original de cada plataforma.

## Compilar

En ARM: `cd picoSargon/ARM`; `./build.ps1 -Board pico2_w -steroids $true` o `-steroids $false`.

En x86: `cd picoSargon/x86/picoSargon`; `./build.ps1 -steroids $true` o `-steroids $false`.

También puede configurarse CMake directamente con `-DSTEROIDS=ON/OFF`. Cada `build.ps1` configura y compila de nuevo.

## Instrumentación

`STEROIDS asp_attempts=... asp_retries=... asp_fail_low=... asp_fail_high=... see_calls=... see_negative=... razor_attempts=... razor_cuts=... nodes=...`.

En ARM la telemetría se imprime mediante `debug_log` al finalizar la búsqueda. En x86 se imprime a `stderr` para no contaminar el protocolo UCI.

- `asp_attempts`: profundidades que comienzan con ventana estrecha; `asp_retries`: re-búsquedas por fail-low/high.
- `see_calls`: recapturas evaluadas; `see_negative`: capturas penalizadas en el ordenamiento, **no podadas**.
- `razor_attempts`: nodos superficiales elegibles; `razor_cuts`: verificaciones quiescence que permitieron retornar.

Los contadores y el trabajo adicional permiten comparar A/B a igualdad de tiempo, profundidad y posiciones. Implementación SEE conservadora que genera capturas legales; no es el SEE bitboard optimizado de Berserk. No extrapolar ventajas NPS antes de medir en RP2350.

## Validación y limitaciones

Sintaxis C++17 con y sin STEROIDS, construcción nativa x86/Linux de la misma lógica, pruebas UCI con grumpy.bin y comprobación de ZIP. **No verificado con MSVC o toolchain RP2350 ni físicamente en Pico 2 W**.
