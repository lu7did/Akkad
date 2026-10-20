# Sargon-NNUE v0.6.120 — LC0 monolítico UCI

## Alcance y prerrequisitos

Parche incremental sobre **v0.6.117 + v0.6.118 + scripts v0.6.119** y la línea de base suministrada. No incluye ni redistribuye `lc0.exe` ni redes LC0. Python requiere `python-chess` para jugar y etiquetar; PyTorch es requerido únicamente para entrenar. Ejecuta el motor `lc0` como proceso UCI mediante `python-chess`; **NO** necesita `lczero-bindings` para el jugador monolítico ni para `--update lc0-uci`.

El player `lc0` usa `evaluator=null`. Es independiente de `player=alphazero` + `evaluator=lc0` (enlaces neuronales). No se cambian los evaluadores históricos ni el método de validación de `sargon_train.py`. Para `lc0.exe` se pueden seleccionar backends GPU o CPU *disponibles en ese ejecutable*. No se requiere GPU.

## Brain de ejemplo

`examples/lc0_uci/brains_lc0_uci.json`:

```json
{
  "schema_version": 1,
  "brains": {
    "lc0_monolithic": {
      "player": "lc0", "evaluator": "null",
      "lc0-uci-path": "data/lc0/lc0.exe",
      "lc0-weights": "data/lc0/model.pb.gz",
      "lc0-backend": "blas", "lc0-uci-nodes": 800,
      "lc0-uci-threads": 1
    }
  }
}
```

En Linux/macOS, editar `lc0-uci-path` al ejecutable real y seleccionar el backend disponible (`blas` para CPU, o el backend local correspondiente). `lc0-uci-options` acepta un JSON de opciones UCI adicionales, validado por el ejecutable (por ejemplo `{"MinibatchSize":32}`). No se deben establecer `UCI_ShowWDL` ni `UCI_Chess960` mediante ese parámetro.

## Uso mediante UCI

```powershell
# LISTEN
.\scripts\sargon_lc0_uci_listen.ps1 -Executable "data\lc0\lc0.exe" -Weights "data\lc0\model.pb.gz" -Backend blas -Nodes 800 -Port 6200

# STDIN
.\scripts\sargon_lc0_uci_stdin.ps1 -Executable "data\lc0\lc0.exe" -Weights "data\lc0\model.pb.gz" -Backend blas

# MATCH: LC0 vs Sargon Plus
.\scripts\sargon_lc0_uci_match.ps1 -Executable "data\lc0\lc0.exe" -Weights "data\lc0\model.pb.gz" -Backend blas -Pairs 2

# SELFPLAY LC0 vs LC0
.\scripts\sargon_lc0_uci_selfplay.ps1 -Executable "data\lc0\lc0.exe" -Weights "data\lc0\model.pb.gz" -Games 2

# RALLY (revisar rutas en brains_lc0_uci.json)
.\scripts\sargon_lc0_uci_rally.ps1 -PreflightOnly
```

Los scripts genéricos `sargon_listen.ps1`, `sargon_stdin.ps1`, `sargon_match.ps1`, `sargon_rally.ps1` y `sargon_selfplay.ps1` siguen funcionando con su sintaxis anterior. En `brains.json` se admite `player=lc0,evaluator=null` con `lc0-uci-path` o `engine-path`. La ejecución mantiene el historial de movimientos disponible hacia Lc0.

## Etiquetado `.pb` independiente

**Trabajar sobre una copia** del `.pb` antes de comenzar (el etiquetado escribe transaccionalmente por partida).

```powershell
.\scripts\sargon_lc0_uci_valor.ps1 -InputPb "data\pb\muestra.pb" -Executable "data\lc0\lc0.exe" -Weights "data\lc0\model.pb.gz" -Backend blas -Nodes 800 -History allow-incomplete
```

Equivalente Python:

```
python -m sargon_nnue.sargon_prepare --input data/pb/muestra.pb --update lc0-uci --lc0-uci-path data/lc0/lc0.exe --lc0-weights data/lc0/model.pb.gz --lc0-backend blas --lc0-uci-nodes 800
```

Se incorporan las columnas `lc0_uci_w`, `lc0_uci_d`, `lc0_uci_l` **orientadas a blancas, normalizadas en [0,1]**, además de `lc0_uci_network_id`, `lc0_uci_engine_id`, `lc0_uci_config_id`, `lc0_uci_history_mode`, `lc0_uci_nodes` y `lc0_uci_depth`. **No** se modifican `w,d,l`, `stockfish_value`, `classic_cp`, `result_value` ni las columnas `lc0_w,d,l` del evaluador neuronal.

El etiquetado exige `UCI_ShowWDL` y el motor debe devolver `info wdl`. Cuando la posición ya es terminal, se registra el resultado legal exacto sin búsqueda. Se intenta reconstruir historial real a partir del PGN indicado en la partida; si no se encuentra, `allow-incomplete` utiliza el estado almacenado con FEN, marcando esa circunstancia. `strict` detiene el proceso. Se exige una red de pesos explícita para poder identificar su hash. El cambio de red o presupuesto requiere una base distinta o `--lc0-uci-overwrite`.

**Estas etiquetas vienen de la búsqueda MCTS interna de `lc0.exe`, no directamente de la salida WDL cruda de la red.** Son etiquetas experimentales distintas de las del evaluador neuronal LC0.

## Entrenamiento con hasta cuatro fuentes (suma 1)

```powershell
.\scripts\sargon_lc0_uci_train.ps1 -InputPb "data\pb\muestra.pb" -OutputDir "data\runs\lc0_uci_001" -WeightClassic 0.15 -WeightStockfish 0.05 -WeightResult 0.40 -WeightLc0 0.40 -Epochs 10 -Validation 10 -Shuffle 20
```

La selección nueva **`--lc0-source uci|neural`** determina de qué conjunto WDL se obtiene el **cuarto maestro**, manteniendo `--weight-lc0` como el único peso LC0. Por defecto `neural` para no cambiar entrenamientos anteriores. No se permite mezclar silenciosamente dos redes LC0 diferentes y las etiquetas ausentes provocan error. El entrenamiento sigue separando partidas enteras para validación dentro de `sargon_train.py`, con muestreo de movimientos posterior. Los checkpoints y metadatos registran la fuente LC0 seleccionada.

Los dos scripts autónomos `run_pipeline_prepare.ps1` y `run_pipeline_train.ps1` ahora aceptan `-Lc0Source uci|neural`; para `uci` también `-Lc0Exe`. PREPARE etiqueta el `.pb` muestreado y TRAIN puede repetirse reemplazando checkpoints con el mecanismo protegido de v0.6.119.

## Pruebas y límites

`python -m compileall -q src/sargon_nnue` valida sintaxis. `PYTHONPATH=src python -m unittest discover -s tests -p test_lc0_uci_v06120.py` valida el contrato de brains y (si está instalado `python-chess`) la orientación WDL. **No se probó aquí la ejecución real de Leela ni los scripts PowerShell sobre Windows/Debian/macOS**: se requiere el binario nativo, un modelo, PowerShell y `python-chess` en el equipo destino.

El parche no incluye binarios, redes ni archivos de configuración existentes del usuario; agregue/actualice los elementos del ZIP en la raíz del repositorio y conserve previamente una copia de seguridad. El ZIP es incremental y solo contiene archivos cambiados o nuevos.
