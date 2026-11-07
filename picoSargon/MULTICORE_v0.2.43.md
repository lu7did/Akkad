# picoSargon v0.2.43 — Listener macOS

Aplica sobre v0.2.42 desde la raiz de akkad.

- `run_listen.sh` inicia en `0.0.0.0:6200` (salvo argumentos o variables explicitas).
- `--help` y `-h` muestran las opciones sin ejecutar el motor. Sin `--cores` ni `PICOSARGON_CORES`, un motor MULTICORE=ON provoca error antes de escuchar.
- Con MULTICORE=ON se exige `--cores N`; con MULTICORE=OFF se rechaza `--cores`. La deteccion se hace consultando `uci` al ejecutable, no suponiendo el modo de compilacion.
- Se admiten `PICOSARGON_CORES=N` y `--cores N` (prevalece el argumento).

Ejemplo:

```bash
./picoSargon/macOS/build.sh
./picoSargon/tools/macos/run_listen.sh --cores 4
```

`--host 127.0.0.1` queda disponible para escucha exclusivamente local.
El valor predeterminado `0.0.0.0` expone TCP en todas las interfaces: usar solo en redes confiables.
