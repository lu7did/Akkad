# picoSargon x86 build v0.2.62 — Validación obligatoria de MULTICORE

Este parche se aplica sobre v0.2.61 y no modifica el algoritmo de búsqueda.

## Problema

Un ejecutable compilado sin `PICOSARGON_MULTICORE` rechaza `--cores`. La preferencia `MULTICORE=ON` en el script no demuestra que el ejecutable seleccionado por `run_uci.py` realmente contenga la opción.

## Verificación de compilación

`tools/ps/build.ps1` comprueba `MULTICORE:BOOL` en `CMakeCache.txt`, retira únicamente `x86/build/picoSargon.exe` antes del build, compila, ejecuta el nuevo binario con `--help` y comprueba que anuncie `--cores` cuando se pidió MULTICORE=ON. Imprime fecha y SHA256 del binario resultante. Fallará en vez de reportar éxito si la opción esperada falta.

Ejecución desde la raíz de Akkad:

```powershell
.\picoSargon\tools\ps\build.ps1 --multicore ON --steroids ON --clean
.\picoSargon\x86\build\picoSargon.exe --help
```

Debe aparecer `--cores 1..1024`. Si sigue sin aparecer, revisar la salida del compilador.

La compilación Windows/MSVC no fue ejecutada en este entorno.
