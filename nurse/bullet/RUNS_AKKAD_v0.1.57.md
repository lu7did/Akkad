# v0.1.57 — propiedad exclusiva de las corridas en Akkad

Base: `lu7did/akkad` `main` commit `7ec16be3e6c0dd5165bfac28b7e6c9a658376694`.

- `bullet_resolve_run_dir` **no examina** `$BULLET_DIR/runs`: solo calcula `$BASE/runs/$RUN_ID` y rechaza enlaces simbólicos en el destino.
- `audit_bullet_layout.sh` deja de inspeccionar o advertir sobre corridas históricas en Bullet externo.
- `tests/test_runs_akkad.py` verifica que los estados antiguos en Bullet no bloquean `--status` y que los estados de Akkad son la única autoridad.
- No se cambia ningún código Rust, arquitectura, entrenamiento ni exportación.
- `migrate_bullet_runs.sh` continúa disponible como herramienta **manual y optativa**; nunca se invoca automáticamente.

Para ejecutar la misma configuración con un nuevo estado, la ausencia de `$BASE/runs/$RUN_ID/MON.state` significa `MON=1`, aun si existe una corrida externa antigua. Esto no borra ni modifica archivos de Bullet externo.

Aplicar descomprimiendo desde la raíz de Akkad. Ejecutar `python3 -m unittest discover -s nurse/bullet/tests -p test_runs_akkad.py -v` y `bash nurse/bullet/run_genesis_mcts.sh --status`.
