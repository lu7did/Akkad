# Bellman-Restricted — importación acumulativa PGN

`bellman_upload.py` importa partidas PGN a una base SQLite `.pb` independiente. No consulta ni calcula posiciones neuronales.

```powershell
python -m sargon_nnue.bellman_upload --path "data\pgn\**\*.pgn" --out "data\bellman_games.pb"
```

- `--path`: admite **glob** (`*.pgn`, `**/*.pgn`) o una expresión regular con prefijo `re:`. Ejemplo: `--path 're:.*partidas.*\.pgn$'` (en Windows, usar rutas completas o relativas con `/` para la expresión regular).
- `--out`: base SQLite `.pb` que se crea si no existe y se amplía si existe.
- Progreso inicial de inventario de archivos, seguido de progreso porcentual sobre archivos y partidas importadas o examinadas.
- Una identidad SHA-256 calculada desde los encabezados PGN normalizados, el resultado y la secuencia de jugadas UCI impide volver a insertar la misma partida, incluso si aparece en dos archivos o cambia el formato de espacios.
- Partidas sin resultado definitivo o con errores de interpretación se omiten y cuentan por separado.
- Registra en `games` el resultado (`0` negras, `1` tablas, `2` blancas) y las medias jugadas, en `pgn_games` el PGN reconstruido (encabezados, línea principal y comentarios), y en `bellman_game_identity` la huella única.
- Conserva las partidas entre ejecuciones y confirma las escrituras por archivo (si falla un archivo no se incorporan datos parciales de él).
- Los datos son compatibles con `bellman_prepare` de **Akkad_Bellman_embedded_PGN_alignment_incremental.zip**, que lee las tablas `games`, `pgn_games` y `meta` y regenera `bellman_actions` dentro de esta misma base.

**Alcance:** se conservan encabezados, línea principal y comentarios; las variaciones secundarias del PGN no se guardan. Para Bellman-Restricted se utilizan únicamente las jugadas de la partida principal.

Dependencia: `python-chess`.
