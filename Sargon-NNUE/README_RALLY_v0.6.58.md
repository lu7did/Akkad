# SARGON RALLY v0.6.58

Organizador de torneo *todos contra todos*. No crea tipos nuevos de motor; delega cada enfrentamiento a `sargon_nnue.sargon_match` mediante `--brain --idA --idB`, sin alterar MATCH.

## Archivos

- `data/brains/brains.json`: registro existente de brains.
- `data/brains/rally.json`: archivo de configuración y resultados; el archivo incluye el mapa `tournaments` donde las claves son los `--id`.
- `scripts/sargon_rally.ps1`: lanzador para Windows PowerShell.

## Ejecución

```powershell
.\scripts\sargon_rally.ps1 --id liga_01 --brain .\data\brains\brains.json --rally .\data\brains\rally.json
```

`--version`, `--help` y `--verbose` también están disponibles. `--python` permite elegir el intérprete de MATCH.

## Definición

- `name`: nombre descriptivo.
- `brains`: IDs de los participantes; como mínimo 2.
- `plays_per_pair`: **partidas** entre dos brains, **debe ser par** para permitir inversión igualitaria de colores con MATCH (`--pairs=plays_per_pair/2`).
- `max_simultaneous_games`: límite de procesos MATCH concurrentes; cada proceso ejecuta una partida a la vez.
- `max_game_seconds`: límite supervisado de duración total de una partida. Si se supera, se aborta el MATCH afectado; el torneo queda `INCOMPLETE` y los resultados previos se conservan.
- `pgn`: destino del PGN consolidado, relativo a la carpeta de `rally.json`.
- `ranking.resultados`: una fila por partida; resultados parciales guardados atómicamente.
- `scores`: clasificación por puntos descendentes con desglose por rival.

Al iniciar, borra `ranking` y `scores` anteriores del torneo seleccionado. Guarda cambios en `rally.json` mientras corre. El directorio de trabajo temporal `.rally_<id>` debe estar vacío o no existir. Antes de relanzar un torneo, archivarlo/eliminarlo manualmente; esto evita repetir partidas por accidente. El programa no reanuda un torneo incompleto automáticamente.

Las partidas incompletas no reciben puntuación. Los archivos CSV/PGN por pareja permanecen disponibles en el directorio temporal. El PGN consolidado se escribe al finalizar, no durante el torneo.

Requiere el mismo entorno Python y dependencias que MATCH, incluido `python-chess`, así como configuraciones de brains válidas y rutas accesibles desde el directorio de ejecución.
