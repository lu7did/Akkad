# picoKeras ARM v0.1.28 (parche incremental)

Aplicar sobre v0.1.27 desde la raíz de Akkad.

- Agrega config/lwipopts.h para el backend Pico SDK `pico_cyw43_arch_lwip_poll`.
- Incorpora `config/` al include path del ejecutable `picoKeras`.
- Actualiza versión a v0.1.28.
- No altera TFLM vendorizado, el modelo ni otros subproyectos.

Compilar desde picoKeras/ARM con `./build.ps1 -Clean` en PowerShell.

La compilación cruzada real debe comprobarse en Windows con el SDK del proyecto.
