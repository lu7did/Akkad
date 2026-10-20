# Sargon-NNUE v0.6.13

Correccion puntual del script `scripts/sargon_stockfish.ps1`.

- El listener `src\sargon-listen.py` se resuelve ahora desde `$PSScriptRoot` y no desde el directorio actual de PowerShell.
- El script puede ejecutarse desde `scripts`, desde la raiz del proyecto o desde cualquier otro directorio.
- Se agregan validaciones explicitas para Python, Stockfish y el listener.
- Se conserva la correccion de v0.6.12: no se fuerza `--network` salvo que el usuario lo indique.
- No se modifican SARGON, SARGON+, las heuristicas de busqueda ni la semantica de `--boost`.
