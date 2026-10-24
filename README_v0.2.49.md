# picoAlpha v0.2.49 — picoExport: salida configurable

Parche incremental sobre v0.2.48; reemplaza solo `picoAlpha/tools/picoDistiller/picoExport.py`.

## Uso predeterminado

`python .\picoExport.py --input "..\data\runs\epoch_best.pt"`

Produce en `picoAlpha/include/`:
- `generated_micro_az_1x8.hpp`
- `generated_micro_az_1x8_fc_int8.hpp`

## Variante independiente

`python .\picoExport.py --input "..\data\runs\epoch_best.pt" --out "..\..\include\variants" --name "picoGyal_zod_e10"`

Produce:
- `picoAlpha/include/variants/picoGyal_zod_e10.hpp`
- `picoAlpha/include/variants/picoGyal_zod_e10_fc_int8.hpp`

`--name` es un nombre base simple, sin extensión ni separadores de directorio. `--out` configura exclusivamente la carpeta.

**Integración:** `net_1x8.cpp` sigue incluyendo los dos nombres predeterminados. Exportar con nombre alternativo archiva una variante, pero **no la selecciona automáticamente para compilar**. Para compilar una variante con el flujo actual, exportar directamente con los nombres predeterminados o copiar sus dos contenidos a los nombres predeterminados antes de compilar. No se toca TinyGyal 2x16.
