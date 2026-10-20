# Sargon-NNUE · división PREPARE / TRAIN · v0.6.119

Este paquete contiene **solo dos scripts PowerShell independientes**, destinados a `scripts/` dentro de Sargon-NNUE. No reemplaza `sargon_pipeline.ps1` ni modifica programas Python. Se basa en el pipeline y los módulos de la integración LC0 **v0.6.117 o posterior**.

## Archivos

- `scripts/run_pipeline_prepare.ps1`: importación de PGN, muestra de partidas, tres etiquetas tradicionales, nueva evaluación **LC0 WDL**, auditoría. **No entrena**.
- `scripts/run_pipeline_train.ps1`: única operación de **entrenamiento PyTorch**; lee la muestra existente y permite cuatro pesos, muestreo de movimientos y reemplazo seguro de checkpoints.

Cada script declara todos sus parámetros localmente; **ninguna variable ni función global compartida**. Ambos pueden ejecutarse desde una sesión nueva y desde cualquier directorio. Los valores predeterminados respetan `lex` y las rutas del `run_pipeline.ps1` adjunto, con dos adiciones: la evaluación LC0 y `MovePercent=20` durante el entrenamiento.

## PREPARE

Ejemplo Windows con GPU Intel si el backend está realmente disponible en los **bindings Python** de LC0:

```powershell
.\scripts\run_pipeline_prepare.ps1 `
    -Python 'C:\Users\pedro\ufasta\Scripts\python.exe' `
    -StockfishExe 'C:\Users\pedro\github\bobby\stockfish\stockfish.exe' `
    -Lc0Weights '..\data\lc0\model.pb.gz' `
    -Lc0Backend 'onnx-dml' `
    -Lc0BackendOptions 'gpu=0' `
    -SamplePercent 20 `
    -Validation 10
```

En CPU, reemplazar `-Lc0Backend onnx-dml -Lc0BackendOptions 'gpu=0'` por `-Lc0Backend blas`, sin opciones de backend.

**Orden:**

1. `import`: incorpora PGN en `data/pb/lex.pb` de forma acumulativa.
2. `sample`: crea `data/pb/lex_sample.pb` con un porcentaje configurable de **partidas completas**. Si ya existe, se reutiliza **sin reconstruirla** y se informa; no modifica el maestro ni el muestreo sin autorización.
3. `evaluate sargon`: actualiza `classic_cp`.
4. `evaluate stockfish`: actualiza `stockfish_value`.
5. `evaluate result`: actualiza `result_value`.
6. `evaluate lc0`: agrega/actualiza WDL y metadatos de LC0 en `positions`.
7. `audit`: reemplaza solamente `audit.json` y `audit.csv` en `data/runs/lex/`.

El programa preexistente calcula las etiquetas en el `.pb` muestreado. LC0 **no se instala ni descarga automáticamente**: debe proporcionarse una red existente y un backend real. El orden de etiquetas se mantiene en llamadas independientes al pipeline.

**Advertencia:** el pipeline maestro no permite sobrescribir la muestra. Para incorporar PGN agregados recientemente al `.pb` maestro en una muestra nueva, utilice explícitamente un `-SamplePb` distinto o conserve respaldos y retire la muestra anterior manualmente. Repetir PREPARE con una muestra existente *no* remuestrea.

## TRAIN

Ejemplo con LC0 al 40 %:

```powershell
.\scripts\run_pipeline_train.ps1 `
    -WeightClassic 0.15 `
    -WeightStockfish 0.05 `
    -WeightResult 0.40 `
    -WeightLc0 0.40 `
    -MovePercent 20 `
    -Validation 10 `
    -Epochs 30 `
    -BatchSize 64 `
    -Device auto
```

Los pesos deben ser no negativos y sumar **1**. Los valores predeterminados sin argumentos son `classic=0.15`, `stockfish=0.05`, `result=0.80`, `lc0=0`; se conserva el entrenamiento previo hasta que se decida asignar peso a LC0. Si se otorga peso positivo a LC0, la base debe contener sus WDL y su metadato de red.

**Muestreo y validación:** `sargon_train.py` reserva el 10 % por partidas completas, y luego selecciona el 20 % (`-MovePercent`) de los **movimientos elegibles del conjunto de entrenamiento**. Validación queda excluida del ajuste de pesos. `-MovePercent` puede ser 100 para entrenar sobre todos esos movimientos. El mismo conjunto de partidas y la misma semilla se vuelven a seleccionar en cada ejecución; cambiar parámetros afecta la nueva corrida, no la base.

**Repetición segura:**

- No modifica `lex_sample.pb`, `lex.pb`, `audit.json` ni `audit.csv`.
- Entrena en `data/runs/lex/checkpoints.__new_<id>/`.
- Verifica que existan `nnue_best.npz` y al menos un `nnue_epoch_XXX.npz`.
- Si termina correctamente, sustituye `data/runs/lex/checkpoints/` y elimina los checkpoints anteriores.
- Si falla la etapa de entrenamiento, los checkpoints anteriores quedan intactos.
- Si hay archivos ajenos a los productos del entrenador en `checkpoints/`, **no los borra**: cancela la operación para evitar pérdida de datos.
- No hace *fine-tuning* del checkpoint previo: **cada invocación inicia una red nueva**, como requiere comparar configuraciones.

El script TRAIN invoca `sargon_nnue.sargon_train` directamente: el wrapper `sargon_pipeline.ps1` de v0.6.117 no transmite `--shuffle` y rechaza directorios con checkpoints previos. No se necesita modificarlo para obtener el comportamiento solicitado.

## Compatibilidad

PowerShell 7 (`pwsh`) es la opción más portable en Windows, Debian y macOS. Ambos scripts aceptan `-Python` o `SARGON_PYTHON`; si no se configura, detectan un Python disponible. En Windows también reconocen el intérprete habitual del entorno `ufasta` si existe. Para Debian/macOS normalmente hay que ajustar `-StockfishExe` y `-Lc0Weights`.

## Verificación

Se contrastaron los argumentos con `sargon_pipeline.ps1`, `sargon_prepare.py` y `sargon_train.py` de la v0.6.117. No hay `pwsh`, GPU LC0 ni un `.pb` real de entrenamiento disponibles en el entorno de pruebas de estos artefactos. **No se declara como validada una ejecución PowerShell extremo a extremo.**
