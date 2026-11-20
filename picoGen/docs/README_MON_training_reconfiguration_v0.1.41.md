# picoGen v0.1.41 — MON reentrante y parámetros de entrenamiento editables

Base de código: `lu7did/Akkad` rama `main`, commit `3f192903aec6012b2ec97f2ae554aa8b98311ec7`, archivo `picoGen/tools/train/run_genesis_binpack.ps1` v0.1.39.

## Defecto reproducible

La línea `--mon 7 --population 50 --generations 100 --mutation-sigma 5` chocaba con `config.lock.json` de una corrida anterior y lanzaba `Configuration lock conflict: Population` incluso cuando el usuario ordenaba repetir el entrenamiento. El archivo también imponía valores anteriores al modificar los defaults de los hiperparámetros.

## Contrato nuevo

* En ejecución explícita `--mon 6` o `--mon 7`, `Population`, `Generations`, `MutationSigma` son configurables por CLI o por los defaults actuales del script. El lock se actualiza al empezar el paso genético y registra los nuevos valores.
* Sin `--mon`, se heredan los últimos valores del lock, se consulta `MON.state` y se reanudan los checkpoints actuales (sin reset).
* La identidad del dataset (T79, T77, cantidades, escaneos, muestras, semilla, CSV compartidos) y el formato siguen inmutables; si cambian se requiere un nuevo `--run-id`.
* En replay explícito, la carpeta anterior del modelo `pst/` o `nnue/` se mueve a `assets/<run-id>/history/<modelo>-<UTC>-<guid>/`. El lock original y el audit anterior se respaldan en esa misma carpeta. No se mezclan generaciones de una corrida nueva con checkpoints previos. La corrida comienza en generación 1.
* Si se cambian hiperparámetros en `--mon 6`, también se archiva y se reinicia NNUE al llegar a MON 7: no se puede reanudar automáticamente un checkpoint NNUE de configuración incompatible.
* Antes de empezar entrenamiento, `MON.state` se escribe con el paso activo, de modo que una interrupción permite un reinicio sin `--mon`.
* `--status` solo consulta estado y no modifica archivos.

Ejemplo:

```powershell
cd C:\Users\pedro\github\bobby\akkad\picoGen\tools\train
.\run_genesis_binpack.ps1 --mon 7 --population 50 --generations 100 --mutation-sigma 5
```

También puede modificarse el valor por defecto del script y usar `--mon 7` para una nueva corrida. La opción de sigma es **desviación estándar de la mutación gaussiana**, no la probabilidad de mutación, que continúa siendo 3 %.

## Consideraciones

No se tocan `genPST.py`, `genNNUE.py`, el fitness, los datasets o los evaluadores. Si solo se repite MON 7 con hiperparámetros distintos, el modelo PST existente conserva su configuración de entrenamiento anterior. La auditoría final evalúa los modelos disponibles, y no equipara necesariamente sus condiciones de entrenamiento.

Esta modificación se revisó estáticamente pero no se ejecutó en Windows PowerShell 5.1 en el entorno de creación.
