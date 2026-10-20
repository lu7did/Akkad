# Sargon-NNUE v0.6.110 — Pipeline genérico

Parche incremental sobre v0.6.109. Solo se reemplaza `scripts/sargon_pipeline.ps1` y se agrega `scripts/run_lex.ps1`.

- Ejecutar: `powershell -File .\scripts\run_lex.ps1`.
- Todas las rutas relativas de parámetros se interpretan desde el directorio que contiene `sargon_pipeline.ps1` (`scripts/`), independientemente del directorio desde el que se invoca.
- Base maestra: `..\data\pb\{nombre}.pb`. La importación acumula PGN en ella si ya existe.
- Base de muestra: `..\data\pb\{nombre}_sample.pb`. Se genera una vez; `-ReuseSample` conserva y vuelve a usar la existente. **No** se sobrescribe silenciosamente.
- Etiquetado independiente in-place: `-Sargon`, `-Stockfish`, `-Result`, al menos uno.
- Los pesos `WeightClassic`, `WeightStockfish` y `WeightResult` son independientes de la elección de los valorizadores; para entrenar con una señal, debe existir su etiqueta en los registros.
- Auditoría: `..\data\runs\{nombre}\audit.json` y `.csv`. Auditoría estructural heredada; no valida la mezcla final ponderada.
- Checkpoints: `..\data\runs\{nombre}\checkpoints\nnue_epoch_001.npz` ... `nnue_best.npz`.
- El pipeline evita sobrescribir un directorio de checkpoints no vacío. Para entrenamientos sucesivos usar otro `RunDir` (o archivar previamente la salida) y `-ReuseSample`.
- Scheduler plateau: LR inicial 0.001, patience 3, factor 0.5, mínimo 0.00001. Los checkpoints se generan por epoch.
- Al ejecutar nuevamente la importación sobre la base maestra, el importador determina cómo tratar PGN ya presentes: compruebe el log de duplicados antes de interpretar el crecimiento de la base.
- No se incluyen ni modifican archivos existentes en `data` o `docs`.

> Nota: `run_lex.ps1` es un ejemplo parametrizable. Cambiar `$nombre` crea otro entrenamiento con rutas predeterminadas coherentes.
