# picoAlpha v0.2.50 — nombre fijo picoGyal

Parche incremental sobre v0.2.49. Solo modifica los tres archivos incluidos; no modifica TinyGyal 2x16.

- `picoExport.py`: por defecto `--name picoGyal`, `--out` predeterminado `picoAlpha/include`.
- `CMakeLists.txt`: para `PICOALPHA_NET=1x8` exige `include/picoGyal.hpp` e `include/picoGyal_fc_int8.hpp`.
- `src/net_1x8.cpp`: incluye ambos archivos nuevos.
- `PICOALPHA_NET=2x16` mantiene sin cambios el evaluador y pesos originales TinyGyal.

Ejemplo desde tools/picoDistiller:

```powershell
python .\picoExport.py --input '..\data\runs\epoch_best.pt'
```

Se crean `picoAlpha/include/picoGyal.hpp` y `picoAlpha/include/picoGyal_fc_int8.hpp`.

`--out` y `--name` siguen disponibles para archivar variantes; CMake utiliza únicamente los nombres fijos indicados arriba, no resuelve automáticamente variantes.
