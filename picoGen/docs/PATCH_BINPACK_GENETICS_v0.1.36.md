# picoGen binpack genetics v0.1.36

Base: v0.1.35. Extraer sobre la raíz de Akkad, sustituyendo `picoGen/tools/train/run_genesis_binpack.ps1`.

- Corrige error de parseo de PowerShell línea 197 (ordenación de checkpoints NNUE): reemplaza `Sort-Object` mal formado por selección de generación máxima mediante bucle.
- Configura directorio por defecto para T79/T77 bajo `C:\Users\pedro\github\Bobby\Chess_History_pb\stockfish` usando `%USERPROFILE%`. No se modifican nombres de datasets, ni algoritmos, ni objetivos.
- Validar con `./run_genesis_binpack.ps1 --status` y luego ejecutar sin argumentos.
- Los archivos reales T79/T77 deben tener los nombres predeterminados o suministrarse con `--train-binpack` y `--valid-binpack`.
- No se ejecutó PowerShell 5.1 en este entorno; se verificó reemplazo de la instrucción defectuosa y ZIP.
