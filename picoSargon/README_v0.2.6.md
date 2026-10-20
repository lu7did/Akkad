# picoSargon v0.2.6 — compilación C++ (parche mínimo)

Corrige `error: 'runtime_error' is not a member of 'std'` en `src/pico_main.cpp`, incluyendo explícitamente los encabezados estándar `<stdexcept>` y `<exception>`.

## Instalación
Reemplazar únicamente `src/pico_main.cpp` en el proyecto picoSargon. Conservar todos los demás archivos de la versión 0.2.5 y los parches anteriores.

## Compilación
```powershell
.\build.ps1
```

Sin cambios en búsqueda, Grumpy, Wi-Fi, UCI o CMake. No hay validación cruzada ARM disponible en el entorno de generación; comprobar en la instalación Windows.
