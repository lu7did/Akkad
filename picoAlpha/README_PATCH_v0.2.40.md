# picoAlpha v0.2.40 — corrección del banner y verificación de aplicación

Parche incremental para la línea v0.2.37–0.2.39. Contiene los tres archivos de la corrección de versionado, sin modificar net.cpp, net_1x8.cpp ni MCTS.

**Importante:** el ZIP tiene una carpeta superior `picoAlpha/`. Extraer desde `C:\Users\pedro\github\Bobby\Akkad` (padre del proyecto), no dentro de `picoAlpha`, para evitar `picoAlpha\picoAlpha`.

Desde `C:\Users\pedro\github\Bobby\Akkad`:

```powershell
Expand-Archive -LiteralPath 'RUTA\picoAlpha_v0.2.40_patch.zip' -DestinationPath . -Force
Select-String -Path '.\picoAlpha\CMakeLists.txt' -Pattern 'project\(picoAlpha_firmware VERSION'
Select-String -Path '.\picoAlpha\CMakeLists.txt' -Pattern 'PA_FIRMWARE_VERSION|configure_file'
```

La versión debe ser 0.2.40 y no debe existir una definición `target_compile_definitions(... PA_FIRMWARE_VERSION=...)`.

Luego, dentro de `picoAlpha`:

```powershell
.\build.ps1
```

CMake debe imprimir `picoAlpha v0.2.40`; el comando del compilador NO debe contener `-DPA_FIRMWARE_VERSION=`. Si imprime otra versión, se están compilando archivos de otra ruta o el parche no fue aplicado sobre el proyecto correcto.

Este parche no fue compilado contra el Pico SDK de Windows en este entorno. No afirma haber validado un UF2.
