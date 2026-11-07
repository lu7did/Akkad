# picoSargon v0.2.44 - Estado MULTICORE en telemetria macOS

Parche incremental sobre v0.2.43. Al arrancar el listener imprime:

`[hh:mm:ss] ⚙️ MULTICORE=True CORE=4`

El estado se deriva del anuncio UCI `option name Cores`. `CORE` es el limite de trabajadores configurado, reducido a los nucleos fisicos disponibles (en macOS, `sysctl hw.physicalcpu`), no el numero de jugadas de raiz que finalmente se asignen. Si MULTICORE esta inactivo, emite `MULTICORE=False CORE=1`. El listener continua exigiendo `--cores N` cuando MULTICORE esta activo.
