# picoGen — Genética sobre Stockfish binpack (v0.1.35)

Base de código: `lu7did/akkad` `main`, commit `98ceccdb758cd57f8b43f1bfb33da6cb990fe94e`.

## Alcance

Se implementa un pipeline NUEVO para Windows. `picoGen/tools/train/archive` queda intacto.
**Sólo** se invocan desde `archive/` los algoritmos genéticos de `genPST.py`, `genNNUE.py`,
`gen_sargon_core.py`, `gen_nnue_core.py`, `gen_progress.py`, `gen_checkpoints.py` y
`gen_nnue_storage.py`. Ningún lector SQLite se ejecuta.

**No requiere Bullet**, Metal, macOS ni PyTorch para entrenar; `sfbinpack=0.6.4` es sólo
un decoder de las posiciones originales de Stockfish. El formato `binpack` contiene
`pos`, `mv`, `score`, `result`, `ply`; `mv` es la jugada registrada, NO el movimiento
preferido mediante MultiPV.

### Prerrequisitos Windows

1. Windows 10/11, Python 3 + PowerShell 5.1+, `pip install -r picoGen/tools/train/requirements.txt`.
2. Rust estable + Cargo: `winget install --id Rustlang.Rustup -e`; cerrar y volver a abrir
   PowerShell; comprobar `rustc --version` y `cargo --version`. Alternativa:
   https://rustup.rs/. `run_genesis_binpack.ps1 --install-rust` solicita la instalación
   mediante winget (no es una instalación silenciosa).
3. Para el toolchain MSVC de Rust en Windows: **Visual Studio Build Tools 2022**,
   componente **Desktop development with C++** (incluye linker y Windows SDK).
4. T79 (entrenamiento) y T77 (validación), dos archivos `.binpack` independientes.
   Por defecto se buscan en `%USERPROFILE%\github\Bobby\stockfish\`, pero puede
   indicar rutas absolutas con `--train-binpack` y `--valid-binpack`.
5. Acceso a crates.io al compilar inicialmente. Se utilizará `sfbinpack=0.6.4`.
   Tras la primera compilación `Cargo.lock` fija las dependencias transitivas.

### Pasos

Desde `akkad\picoGen\tools\train`:

```powershell
python -m pip install -r .\requirements.txt
.\run_genesis_binpack.ps1 --help
.\run_genesis_binpack.ps1 --mon 1 --train-binpack 'D:\Stockfish\T79.binpack' --valid-binpack 'D:\Stockfish\T77.binpack'
.\run_genesis_binpack.ps1 --status
```

La cadena completa MON 1..8 incrementa automáticamente el estado. Las opciones
relevantes deben mantenerse idénticas en sucesivas invocaciones de un mismo RUN_ID.
Para una segunda corrida use `--run-id otro-id`. Para un piloto corto, establezca
`--train-count 25000 --valid-count 5000 --train-scan 250000 --valid-scan 50000`
y `--fitness-sample 2500 --validation-sample 500 --population 10 --generations 3`.

**Estado y todos los resultados** bajo `picoGen/assets/<RUN_ID>/`:
CSV, hashes de datos, `MON.state`, `config.lock.json`, `pst/best.json`, checkpoints
PST, `nnue/best.npy`, `nnue/best.active.json`, snapshots NNUE y `audit.json`.

## Contrato de datos

`record_id,source_chunk,fen,ply,played_uci,score_stm_cp,score_white_cp,result_stm,result_white`.

`score_stm_cp` es la etiqueta `score` desde el bando al turno; `score_white_cp`
es su conversión a perspectiva blanca, recortada a ±2000 cp por compatibilidad
con la función objetivo actual de picoGen. El campo raw conserva el score original.
Las entradas con `ply < 16` o `|score| > 10000` se descartan, siguiendo el filtro
usado en el pipeline Bullet MCTS. Para las restantes se aplica reservoir sampling
reproducible sobre las primeras `--*-scan` entradas elegibles; no se mezclan T79
ni T77. `source_chunk` representa un *chunk* binpack, **no** un identificador de
partida fiable. No se afirma separación por partida. Se comparan estados de tablero
idénticos en las muestras seleccionadas, con exclusión de las posiciones superpuestas de T77.

El archivo contiene `played_uci` solo para rastreo; los entrenadores actuales
optimizan MSE de centipeones, **no** acierto de jugadas o políticas MCTS.

## Elecciones metodológicas explícitas

Se mantiene el núcleo genético aprobado: PST por ruleta/elitismo/cruce/bit-flip;
NNUE 768x16 int16, élites 5, top20, cruce un punto, mutación 3% ±6, fitness
`-MSE` sin reescalado. Se cambia únicamente el origen de datos y la evaluación
sobre un lote fijo por corrida (por defecto 10.000 posiciones), idéntico para
cada individuo y generación. El reservorio CSV es por defecto 1.000.000 filas;
el millón no se evalúa por individuo. T77 se reserva como validación.
El entrenador archivado calcula la validación como diagnóstico; nunca participa
en la selección genética.

**Riesgo no resuelto:** no se demostró que el dataset SQLite fuera la única
causa de no convergencia. Tampoco se ha compilado Rust contra binpacks reales
en Windows desde este entorno; no confundir tests del adaptador con una prueba
completa de entrenamiento. T79/T77 deben obtenerse legalmente por separado.

## Pruebas

```powershell
python -m unittest discover -s .\tests -p 'test_binpack_csv_v0135.py' -v
cargo test --manifest-path .\binpack\Cargo.toml
```

La carpeta `assets/` está ignorada actualmente por el `.gitignore` general de Akkad.
Está bajo el árbol del proyecto LOCAL, pero los pesos y checkpoints **no se incorporan
automáticamente a Git**. Para versionar artefactos voluminosos, gestionar Git LFS
explícitamente; no añadir un millón de posiciones CSV al repositorio normal.
