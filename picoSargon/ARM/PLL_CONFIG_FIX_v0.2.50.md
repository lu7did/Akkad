# picoSargon ARM - v0.2.50

Parche incremental para aplicar despues del parche Bashful v0.2.49.
No modifica `include/config.h` ni los pesos NNUE.

## Correccion
- BOOT utiliza `runtime_config::UCI_NAME`, no la version fija v0.2.49.
- build.ps1 lee PLL_SYS de include/config.h, muestra la ruta y valor y pasa el valor esperado a CMake.
- static_assert en pico_main.cpp falla si el compilador ve otro PLL_SYS.
- No cambia el algoritmo de reloj ni elimina los CLOUD_HOOK preexistentes. La separacion arquitectonica picoPixie/picoSargon queda pendiente de parche independiente.

## Limitaciones
- No se realizo compilacion cruzada ARM ni prueba de hardware en este entorno.
- La verificacion valida la configuracion de la compilacion, no demuestra que se haya flasheado el nuevo UF2.
