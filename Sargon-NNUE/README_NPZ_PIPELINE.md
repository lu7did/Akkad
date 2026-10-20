# Sargon NPZ: preparación y entrenamiento v1.0.0

Dependencias: Python 3.10+, `numpy`, `chess` (python-chess) instalados mediante `pip install -e .`.

Preparación, sin Stockfish:

```bash
python src/sargon-prepare.py --dir 'data/pgn/*.pgn' --out data/train.pb
```

Con Stockfish WDL (se evalúa la posición **posterior** a cada movimiento):

```bash
python src/sargon-prepare.py --dir 'data/pgn/fis*.pgn' --out data/train_sf.pb --stockfish --stockfish-path /path/to/stockfish --stockfish-depth 12 --stockfish-threads 1
```

Entrenamiento (1% de partidas retenidas, 10 épocas, Adam por defecto):

```bash
python src/sargon-train.py --input data/train_sf.pb --nnuedir data/nnue/npz/new --epoch 10 --validation 1 --stockfish --weight-stockfish 0.5
```

`--dir` interpreta **glob**, no expresiones regulares, y funciona en Windows, macOS y Linux. Siempre entrecomillar el patrón. El archivo `.pb` es SQLite versionado: no es Google Protocol Buffers. El orden de partidas/posiciones originales no cambia; los índices aleatorios se construyen durante el entrenamiento y se regeneran por época.

### Compatibilidad

El evaluador NPZ exige **781-64-1** (50.114 parámetros: 781×64 + 64 + 64 + 1 + 1). Las redes antiguas **781-32-1** son incompatibles y se rechazan claramente. Se debe entrenar una red nueva, o diseñar separadamente un procedimiento explícito de migración de pesos. El formato de nombres `w_ih`, `b_h`, `w_ho`, `b_o`, `hm_w` permanece.

Los registros almacenan las 781 entradas binarias codificadas por el **mismo** codificador que la inferencia, más `halfmove` (la entrada escalar lateral); WDL de blancas en milésimos; procedencia PGN/STOCKFISH/TERMINAL; partida y orden original. Las partidas inválidas se rechazan de forma íntegra.

`--weight-stockfish` solo existe en entrenamiento. Con valor cero, el objetivo es el PGN sin importar `--stockfish`; para peso positivo requiere WDL real. Se usa `T=(1-z₂)R+z₂(W+D/2)/1000` con `R=0,0.5,1`. Entrenamiento Adam con batches, shuffle nuevo por epoch, MSE online de entrenamiento y MSE de validación sin modificar pesos. La validación es por partida, no por posición.

Los checkpoints se escriben atómicamente después de cada epoch; se conserva un manifiesto de split e índice temporal de posiciones. Para reanudar *exactamente* Adam desde checkpoint sería necesario persistir también sus momentos y estado RNG; la opción `--network` solo permite **inicializar pesos**, no promete reanudación exacta.

**Advertencias:** las partidas duplicadas entre archivos pueden contaminar validación; el código no deduplica PGN. `--validation 0` desactiva MSE de validación. El WDL de Stockfish depende de la versión y configuración del motor. El evaluador conserva la proyección bruta `int(raw*400)` de la versión previa, sin afirmar que sea una calibración WDL universal.
