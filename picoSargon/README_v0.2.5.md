# picoSargon v0.2.5 — parche de rutas host

Sustituir exclusivamente `build.ps1` en la raíz del proyecto existente. Conservar `CMakeLists.txt` y `config/lwipopts.h` de v0.2.2.

Rutas confirmadas:
- `pioasm`: `C:\Users\pedro\.pico-sdk\tools\2.3.1\pioasm`
- `picotool`: `C:\Users\pedro\.pico-sdk\picotool\2.3.1\picotool`

La búsqueda v0.2.4 de `pioasm-config.cmake` era incorrecta; el archivo instalado es `pioasmConfig.cmake`. Se emplea `-Dpioasm_DIR` y `-Dpicotool_DIR` para pasar sus directorios a CMake. Nuevo directorio de construcción: `build-pico-w-v025`.

Ejecutar desde PowerShell: ` .\build.ps1 `.

**Pendiente de validar en Windows:** presencia del archivo de configuración de `picotool`, configuración y compilación final. Si el script indica que falta configuración `picotool`, listar esa carpeta para identificar el nombre real. No se modifica ninguna variable de entorno persistente.
