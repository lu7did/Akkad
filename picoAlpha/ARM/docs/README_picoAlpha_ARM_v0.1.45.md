# picoAlpha ARM v0.1.45 — corrección de cabeceras lwIP

## Error reproducido

`fatal error: lwipopts.h: No such file or directory` durante la compilación de `src/pico_main.cpp`, SDK 2.3.1, GCC ARM 15.2.1.

## Cambios

- `CMakeLists.txt` incluye la configuración **existente** `../../picoSargon/ARM/config/lwipopts.h`. No se copia ni duplica.
- Se sincronizan `PICOALPHA_MDNS_COMPILED` y `PICOSARGON_MDNS_COMPILED` para que la definición de mDNS que utiliza ese archivo corresponda a la biblioteca seleccionada por CMake.
- Versión uniforme `0.1.45` en CMake y `include/config.h`.
- Documentación dentro de `picoAlpha/ARM/docs/`.

## Aplicación

Descomprimir el ZIP en la raíz `akkad`, sobrescribiendo tres archivos. Para cumplir la regla de documentación, eliminar el antiguo `picoAlpha/ARM/README.md` introducido por v0.1.43; su contenido se copia ahora a `picoAlpha/ARM/docs/README.md`. El ZIP no elimina archivos preexistentes.

Reconstruir desde `picoAlpha/ARM` ejecutando `./build.ps1` o `tools/ps/build.ps1`. Si CMake mantiene una caché antigua, borrar únicamente el directorio de construcción específico del firmware y volver a configurar.

## Alcance de validación

Se verificó estáticamente la ruta real de `lwipopts.h` y las macros utilizadas por ese encabezado en el código picoSargon. No se ejecutó compilación cruzada ni prueba física en Raspberry Pi Pico 2W desde este entorno.
