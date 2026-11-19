# Akkad / nurse / bullet — resultados persistentes v0.1.56

Base: GitHub `lu7did/akkad` main, commit `73902c294d47e6aad4065e7f1e09597bff374bfe`; scripts base v0.1.55 (parche previo).

## Contrato de directorios

- `akkad/nurse/bullet`: scripts, Rust/Python y `runs/<RUN_ID>/` completos (checkpoints, estado MON, optimizer, exportaciones, CSV y logs).
- `$BULLET_DIR`: instalación **externa** de Bullet Rust/Metal. Sigue conteniendo `Cargo.toml`, `crates`, `examples` y `target`. Los scripts hacen `cd "$BULLET_DIR"` para `cargo`, sin cambiar dónde escriben resultados.
- Datasets T79/T77: siguen en sus ubicaciones externas y se usan por ruta absoluta.
- Los cuatro pipelines pasan rutas absolutas de salida a los entrenadores; picoBit genera sus ejemplos Rust con rutas absolutas nuevas.
- `config.lock` se mantiene idéntico en una migración porque no incluía `RUN_DIR`; no se cambia MON ni `RUN_ID`.
- `RUNS_ROOT` no es configurable deliberadamente: protege la propiedad de Akkad sobre los checkpoints.

## Migración obligatoria de corridas existentes

**Hacer antes de ejecutar de nuevo el entrenamiento**. Desde `akkad/nurse/bullet`:

```bash
bash migrate_bullet_runs.sh --run grumpy-bullet-001 \
                            --run bnn-bullet-001 \
                            --run mcts-bullet-rust-001 \
                            --run picobit-nnue-003
bash audit_bullet_layout.sh
bash run_genesis_mcts.sh --status
```

Elegir solo IDs que realmente existen. `--all` puede copiar también corridas ajenas a Akkad. La migración preserva originales en Bullet, verifica cada archivo recursivamente y falla si el destino ya existe, para no fusionar experimentos. Tras verificar y hacer backup se pueden borrar manualmente las copias antiguas; el script nunca las elimina.

## Git

Los resultados dentro de Akkad quedan bajo su control de directorios, **no automáticamente bajo control de versiones**. `git add` es explícito; los checkpoints y el estado del optimizador pueden ser grandes. Antes de subirlos decidir Git LFS o almacenamiento de artefactos y revisar las reglas de `.gitignore`; no hay una política de versionado de pesos impuesta por este parche.

## Observaciones

La migración no reescribe referencias absolutas guardadas dentro de logs históricos ni un manifiesto externo. `config.lock` almacena `BULLET_DIR`, no `RUN_DIR`, por lo que puede reutilizarse. `--mon 2` de picoBit regenera sus ejemplos Rust usando el nuevo path; si ya se habían compilado con la ruta vieja y se necesita reanudar, ejecutar MON 2 antes de MON 4. En Grumpy/BNN/MCTS los paths se leen desde variables exportadas al ejecutar.
