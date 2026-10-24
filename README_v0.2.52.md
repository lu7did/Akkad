# picoAlpha v0.2.52 — limite temporal unico

Parche incremental para v0.2.51.

## Aplicacion

1. Extraer ZIP en el directorio que contiene `picoAlpha`, sobrescribiendo solo `picoAlpha/src/pico_main.cpp` y `picoAlpha/CMakeLists.txt`.
2. Desde ese directorio, ejecutar `python apply_v0.2.52.py`. Este paso elimina **solo** `TIMEOUT_MS` de tu `picoAlpha/include/config.h` local; conserva TMAX_MS, SSID, contrasena, simulaciones y el resto de las opciones.
3. Compilar normalmente con `build.ps1`.

## Cambios

- `TMAX_MS` es el unico presupuesto de tiempo de busqueda. `0` conserva el significado de sin limite temporal propio.
- `tout` del banner informa `TMAX_MS`.
- CMake identifica version 0.2.52.
- No modifica MCTS, NN, pesos, memoria, Wi-Fi ni protocolo UCI.

Nota: No incluir un `config.h` completo evita sobrescribir credenciales y personalizaciones locales.
