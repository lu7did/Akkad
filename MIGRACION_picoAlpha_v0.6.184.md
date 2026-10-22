# Akkad v0.6.184 — reubicación del firmware picoAlpha

El firmware Raspberry `picoAlpha` es un proyecto autónomo, hermano de `picoSargon` y `Sargon-NNUE`.

Estructura esperada (descomprimir **dentro de la raíz que contiene Akkad**, o copiar el contenido de `Akkad/` a su directorio Akkad):

```
Akkad/
  Sargon-NNUE/         (sin cambios)
  picoSargon/          (sin cambios)
  picoAlpha/           (firmware Raspberry, autónomo)
    CMakeLists.txt
    build.ps1
    pico_sdk_import.cmake
    include/
    src/
    tools/
```

**Eliminación necesaria:** tras verificar que el nuevo `Akkad/picoAlpha` está íntegro, eliminar la carpeta obsoleta `Akkad/Sargon-NNUE/firmware/picoAlpha`. No borrar `Akkad/Sargon-NNUE/native/picoAlpha`, que es el motor para Windows.

Compilar desde `Akkad/picoAlpha` usando `./build.ps1` (Pico 2 W por defecto), o `./build.ps1 -Board pico_w` (Pico W experimental). Las rutas del script se resuelven desde `$PSScriptRoot`, por lo que no dependen del directorio anterior. El modelo convertido `include/generated_tinygyal.hpp` está incluido.

Este parche solo cambia la ubicación de archivos del firmware; no modifica su lógica ni los proyectos hermanos. No incluye binarios UF2; compilar y validar en la plataforma destino.
