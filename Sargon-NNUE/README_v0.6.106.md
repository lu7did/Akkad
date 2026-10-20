# Sargon-NNUE v0.6.106 — preparación y combinación de señales

El parche conserva los directorios `data/` y `docs/` existentes: NO los incluye ni elimina archivos. Descomprimir en la raíz de Sargon-NNUE con preservación de archivos existentes.

## Preparación

Carga acumulativa PGN: `python -m sargon_nnue.sargon_prepare --dir 'data/pgn/a*.pgn' --out data/partidas.pb`.

Subdirectorios: `--dir 'data/pgn/Fis*/*'` (en Windows también se acepta `\\`).

Por cada archivo, `source` y `source_index` impiden duplicados al repetir exactamente esa carga. No es desduplicación por contenido: copias con nombres diferentes pueden duplicar partidas.

Muestra aleatoria por partidas completas: `python -m sargon_nnue.sargon_prepare --input data/partidas.pb --resample 20 --out data/muestra.pb --seed 42`; necesita `--override` para reemplazar la muestra anterior.

Las tres actualizaciones se ejecutan **independientemente** sobre la misma base:

- `python -m sargon_nnue.sargon_prepare --input data/muestra.pb --update classic`
- `python -m sargon_nnue.sargon_prepare --input data/muestra.pb --update stockfish --stockfish-path C:\\ruta\\stockfish.exe --stockfish-depth 12`
- `python -m sargon_nnue.sargon_prepare --input data/muestra.pb --update result --result-smoothing 0.15`

Las etiquetas son `classic_cp` (centipeones, orientados a blancas), `stockfish_value` (expectativa WDL de blancas [0,1]) y `result_value` (resultado de partida suavizado [0,1]). La normalización del valor CLASSIC durante entrenamiento es `sigmoid(classic_cp/400)`.

Suavizado: `0.5 + (resultado_blancas-0.5)*(ply/total_plies)^(1/factor)`; el valor converge al resultado real y evita la asignación de resultado final a la totalidad de movimientos.

## Entrenamiento PyTorch

`python -m sargon_nnue.sargon_train --input data/muestra.pb --nnuedir data/nnue_run --pytorch --classic --stockfish --weight-classic 0.3 --weight-stockfish 0.5 --weight-result 0.2 --epoch 30 --validation 10`

Se exigen pesos no negativos que sumen 1. Si se omite `--weight-result`, recibe el remanente. Para una única etiqueta use 1.0 en su peso y 0.0 en el resto. Se requiere que cada posición tenga las etiquetas activas, sin sustituciones silenciosas. La partición de entrenamiento/validación permanece **disjunta por partida** (protección contra fuga de información por posiciones correlacionadas). `--shuffle` elige una proporción de jugadas del conjunto de entrenamiento sin reemplazo.

Por defecto el scheduler PyTorch es `plateau` y se guarda `nnue_best.npz` al mejorar la MSE de validación. Puede elegirse `--scheduler none`, `cosine` o `step`.

## Límites de la v0.6.106

La ruta histórica de entrenamiento NumPy continúa disponible solo para entrenamiento PGN sin mezcla. Los modos heredados `--fine-tune` aún conservan su semántica histórica y no se deben usar con el nuevo objetivo mezclado sin una revisión separada. La retrocompatibilidad de checkpoints depende de que se utilice la salida sigmoid de la arquitectura 781-64-1.

La instalación de prueba carece de `python-chess`; se verificó sintaxis y estructura del archivo, **no una prueba de punta a punta con partidas reales**. Probar primero sobre copias de las bases y no sobre la base maestra.
