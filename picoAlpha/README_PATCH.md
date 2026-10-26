# picoAlpha x86 v0.2.78 — build.ps1 único

Parche incremental sobre picoAlpha x86 v0.2.77. Extraer en raíz de picoAlpha preservando `x86/picoAlpha/build.ps1`.

Ejecutar `cd x86/picoAlpha; .\build.ps1`. Cada ejecución configura CMake explícitamente con `PA_X86_FC1_TILED=ON` y Release, y después compila los dos ejecutables (`picoAlpha.exe` INT8 y `picoAlpha32.exe` de referencia FP32).

La selección de arquitectura de red no es una opción de compilación: se mantiene la carga directa desde archivos LC0 `.pb.gz`, admitiendo solo TinyGyal 2x16 y picoGyal 1x8, con el lector propio protobuf/gzip y sin utilizar API LC0.

Requisitos heredados del proyecto: CMake, Visual Studio con herramientas C++, vcpkg y zlib. El script usa por defecto el generador `Visual Studio 18 2026` y la arquitectura x64, igual que la línea de base. Si el entorno usa otro generador, los parámetros `-Generator` y `-Architecture` siguen disponibles; no se necesita activar opciones individuales de optimización.

Comprobación efectuada: comparación textual de la opción CMake existente y sintaxis estructural del script. PowerShell/Visual Studio no están disponibles para validar compilación Windows en este contenedor.
