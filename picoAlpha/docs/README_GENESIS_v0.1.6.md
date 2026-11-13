# picoAlpha Genesis — v0.1.6

Parche incremental sobre v0.1.5; sustituye únicamente `picoAlpha/tools/train/run_genesis.ps1`.

## Corrección

En el paso 3 se construía `--args ''` incluso cuando `EngineArgs` era vacío. Al enlazar el array `Arguments` a `Invoke-GenesisStep`, PowerShell podía emitir `ParameterArgumentValidationErrorEmptyStringNotAllowed` antes de ejecutar `teacher.py`. Ahora `--args` se omite cuando no hay argumentos de motor, aprovechando el valor por defecto de `teacher.py`. Si `-EngineArgs` tiene contenido, se pasa sin alteraciones.

## Reanudación obligatoria

`-Mon N` (alias `--mon N`, para PowerShell compatible) es obligatorio en todo arranque de trabajo. Valores válidos 0..5; sin él se produce un error antes de crear directorios o invocar procesos. `-Help` funciona sin `-Mon`.

Ejemplos:

```powershell
.\run_genesis.ps1 -Mon 0  # empieza de cero; ELIMINA history.pb
.\run_genesis.ps1 -Mon 3  # reanuda teacher; NO vuelve a ejecutar sampler
.\run_genesis.ps1 -Mon 4  # reanuda train
.\run_genesis.ps1 -Mon 5  # exporta desde best.pt existente
.\run_genesis.ps1 -Help
```

Al iniciar en el paso N, se omiten todos los pasos anteriores. Al terminar correctamente cada paso, MON aumenta en uno y se continúa hasta el final; ante un error se detiene. Se valida la base de muestra existente antes de `teacher.py` y `train.py`, y `best.pt` antes de exportar.

**Precaución:** `-Mon 0` vuelve a ejecutar `create.py` y borra el histórico; `-Mon 2` regenera la muestra. Para recuperar del error observado inmediatamente después del paso 2 usar `-Mon 3`.

## Limitación de pruebas

Revisado estáticamente el código y su contrato de argumentos; no se ejecutó PowerShell nativo ni Stockfish desde este entorno. La ejecución final deberá verificarse en Windows.
