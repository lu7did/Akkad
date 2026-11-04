# picoKeras/ARM v0.1.25 — CMake + Ninja, sin MSYS2

Base exclusiva: `akkad(20261104-003050).zip`. Descomprimir este parche desde la raíz `Akkad/`.

- `build.ps1` conserva modelo, SDK, toolchain, WiFi y opciones previas.
- Por defecto, CMake compila `tensorflow_microlite` desde `third_party/tflm-tree`, con fuentes seleccionadas a partir del `sources.inc` de la versión incluida.
- No se invoca Bash, MSYS2, GNU Make ni `pacman`.
- `-TflmLibrary RUTA.a` sigue disponible para utilizar un archivo ARM precompilado.
- Si faltan cabeceras FlatBuffers y no se indicó `-NoDownload`, se preparan con Python nativo de PowerShell.
- Firmware esperado: `picoKeras/ARM/build-pico2-w/picoKeras.uf2`.

La selección de operadores es la incluida en `sources.inc` de la base; la eliminación de código no utilizado depende del enlazador y de `-ffunction-sections`.

**Validación realizada**: integridad del ZIP, verificación de rutas/fuentes declaradas y consistencia del parche. **No validado**: compilación cruzada en Windows ni ejecución en Pico 2 W (toolchain/SDK físicos no disponibles en el entorno de generación).
