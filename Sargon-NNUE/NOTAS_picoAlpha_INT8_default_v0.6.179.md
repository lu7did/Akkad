# picoAlpha INT8 predeterminado — v0.6.179

- picoAlpha.exe ejecuta INT8 por defecto.
- picoAlphaFP32.exe conserva FP32 por defecto como referencia.
- `--precision int8|fp32` sigue permitiendo elegir explicitamente la precision.
- El adaptador Python no se modifica: apunta al ejecutable indicado por `engine-path`.
- Cambios exclusivos a CMakeLists.txt, build_windows.ps1 y documentacion; sin cambios en algoritmo ni código fuente C++.
- Ambos targets compilados en Linux con CMake; compilacion Windows pendiente.
