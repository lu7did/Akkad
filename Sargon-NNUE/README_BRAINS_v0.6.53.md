# SARGON-NNUE v0.6.53 — Brain Registry

Un **brain** es una combinación nominada de player/evaluator y sus opciones de motor. Archivo único `brain.json` con raíz `{"schema_version": 1, "brains": {"id": {...}}}`. Los nombres de los players/evaluadores siguen siendo los de la CLI; no se generan nuevos tipos.

## Crear y listar

```powershell
.\scripts\sargon_brainmaker.ps1 --brain .\brain.json --id rapido --player sargon-plus --evaluator classic
.\scripts\sargon_brainmaker.ps1 --brain .\brain.json --list
.\scripts\sargon_brainmaker.ps1 --brain .\brain.json --list rapido
```

Brainmaker no sobrescribe un ID existente. Los campos sin valores por defecto siguen como null: editar el JSON para establecer las rutas `network`, `engine-path` o `stockfish-path` antes de usarlo. Las opciones explícitas en la línea de comandos tienen prioridad sobre el brain; no se leen ni alteran opciones del supervisor (puerto, tiempos globales de MATCH, archivos PGN/CSV o auditoría).

## Ejemplos

```powershell
.\scripts\sargon_listen.ps1 --brain .\brain.json --id sargon_rapido --mode TCP --port 6200
.\scripts\sargon_stdin.ps1 --brain .\brain.json --id sargon_profundo
.\scripts\sargon_selfplay.ps1 --brain .\brain.json --idA sargon_rapido --idB sargon_profundo --games 20
.\scripts\sargon_match.ps1 --brain .\brain.json --idA sargon_rapido --idB sargon_profundo --pairs 15 --csv data/match.csv
```

Los lanzadores PREPARE/TRAIN/AUDIT/JUDGE conservan sus parámetros originales; no instancian jugadores y por eso no leen perfiles brain. Sus opciones obligatorias son documentadas mediante `--help` en cada módulo. Todos los `.ps1` utilizan el Python del venv `ufasta` si está disponible, y otro `python` de PATH en caso contrario.

**Alcance:** la versión incluye cambios dirigidos a las CLI del listener, MATCH y SELFPLAY. No se ha certificado aquí una partida UCI completa. Revisar `--help` antes de ejecutar.
