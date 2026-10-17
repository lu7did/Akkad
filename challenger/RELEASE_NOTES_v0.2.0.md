# Challenger v0.2.0

## Cambios

- Nuevo brain `random`, que selecciona uniformemente entre las jugadas legales de la posición.
- El brain `random` utiliza el controlador existente de Challenger, por lo que conserva relojes, validación de legalidad, reglas terminales, PGN, JSON e informe de resultado.
- Se expone `--qdepth` en CLI. Default: `2`, igual al valor que antes estaba implícito en `SargonEngine`.
- `SargonBrain` pasa explícitamente `plies` y `qdepth` a `SargonEngine`.
- El GUI muestra `Depth/QDepth` para Sargon y `n/a` para brains a los que no aplica.
- `scripts/challenger_sargon.ps1` expone `$QDepth`.
- Se agrega `scripts/challenger_random.ps1`.

No se modificaron las reglas de terminación ni los brains Stockfish/Human.
