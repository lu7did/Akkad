# picoSargon v0.2.17 — STEROIDS ON por defecto

Parche incremental sobre v0.2.16. Extraer en la raíz `Akkad/`.

Archivos modificados: `picoSargon/ARM/build.ps1` y `picoSargon/x86/picoSargon/build.ps1`.

Cambios: el argumento PowerShell `[bool]$steroids` ahora tiene valor por defecto `$true` en ambos scripts. No se altera CMake, motor, red Grumpy ni telemetría. Las tres técnicas Aspiration Windows, SEE y Razoring quedan compiladas por defecto **si se invoca build.ps1**.

- ARM: `./build.ps1 -Board pico2_w` o desactivar con `./build.ps1 -Board pico2_w -steroids $false`.
- x86: `./build.ps1` o desactivar con `./build.ps1 -steroids $false`.

Nota: invocar CMake o build_host.py directamente no utiliza el valor predeterminado del script PowerShell.
