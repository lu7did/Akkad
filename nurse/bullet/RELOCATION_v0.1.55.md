# Akkad / Nurse / Bullet — separación de fuentes y runtime v0.1.55

**Base auditada:** `lu7did/akkad`, `main`, commit `73902c294d47e6aad4065e7f1e09597bff374bfe`.

## Arquitectura de directorios

- **Código fuente controlado por Git:** `akkad/nurse/bullet/` y sus módulos `grumpy_genesis`, `bnn_genesis`, `mcts_genesis`. Los scripts resuelven su directorio de fuentes a partir de `BASH_SOURCE`, sin depender de `pwd`.
- **Runtime Rust/Metal:** instalación independiente `~/github/Bobby/bullet` (o la ruta indicada en `BULLET_DIR`). Su `Cargo.toml`, `crates/`, `examples/`, `target/` y `runs/` siguen siendo propiedad de esa instalación.
- **Datos:** T79 y T77 en `~/stockfish`, con sobrescritura explícita mediante `TRAIN_DATA` y `VALID_DATA` en los tres programas genesis. La cadena picoBit conserva su configuración histórica interna.
- **Checkpoints:** permanecen en `BULLET_DIR/runs/<RUN_ID>` para no cargar a Git con datos masivos. El parche no mueve ni elimina checkpoints.

## Diagnóstico comprobado

- Los tres `run_genesis*.sh` de la base ya referenciaban sus fuentes mediante `dirname(BASH_SOURCE)` y hacían `cd "$BULLET_DIR"`, por lo que **no se pudo demostrar que el traslado, por sí solo, los rompiera**. Sin un log de la falla original no debe atribuirse a la ruta sin más pruebas. Se reforzó la detección de la instalación y el registro de ejemplos.
- `picobit_pipeline.sh` sí tenía una dependencia externa no incorporada a Akkad: `examples/pico_bit_{train,validate,parity}.rs`. No figuran en el árbol `nurse/bullet` de la base. El script ahora los consume desde `nurse/bullet/picobit_genesis/`; si faltan, ejecuta una importación **sin sobreescritura** desde los originales que permanezcan en Bullet. Después deben incorporarse a Git con `git add nurse/bullet/picobit_genesis`.
- Si los tres `.rs` ya se borraron de Bullet y no están en Akkad, hay que recuperarlos de la copia histórica. El parche **no fabrica** archivos Rust que desconoce.

## Uso en macOS

```bash
cd ~/github/bobby/akkad/nurse/bullet
bash audit_bullet_layout.sh
bash run_genesis.sh --status
bash run_genesis_bnn.sh --status
bash run_genesis_mcts.sh --status
bash picobit_pipeline.sh --status
```

Si Bullet no se encuentra automáticamente, definir su ruta real una vez:

```bash
export BULLET_DIR=/Users/pedrocolla/github/bobby/bullet
```

Ejecutar a continuación, según el modelo:

```bash
bash run_genesis.sh --mon 2
bash run_genesis_bnn.sh --mon 2
bash run_genesis_mcts.sh --mon 2
bash picobit_pipeline.sh --mon 1
```

La opción `--mon 2` reinstala y recompila ejemplos desde las fuentes de Akkad. Si existen checkpoints, el entrenador puede reanudarlos; no se borran ni se sobrescriben explícitamente los archivos de estado. Antes de reanudar una ejecución, consultar `--status` y preferir invocar sin `--mon` si el estado guardado ya es posterior.

## Verificación y límites

El parche fue comprobado con `bash -n`, pruebas Python de rutas, smoke tests de MON 1/2 usando un runtime Bullet simulado y verificación de ZIP. No se ha compilado con Rust/Metal en esta máquina y, sin un log de la ejecución original después de mover carpetas, no es posible demostrar que todos los fallos del entorno hayan desaparecido.

**No modifica** la arquitectura ni etiquetas de ninguna red, optimizadores, nombres de modelos, formatos de salida, datasets, parámetros de entrenamiento o checkpoint. El único cambio en la fuente de Rust que se copia a Bullet es ninguno: se conserva la existente y se modifica dónde se lee.
