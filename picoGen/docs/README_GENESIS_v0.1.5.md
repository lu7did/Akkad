# picoGenus Genesis v0.1.5

Script `picoGenus/tools/train/run_genesis.ps1` reemplaza la secuencia de cuatro comandos suministrada, sin modificar los programas Python.

## Ejecucion

```powershell
.\run_genesis.ps1 --help
.\run_genesis.ps1 -Mon 1
.\run_genesis.ps1 -Mon 3 -SampleDb 'D:\chess\genus.pb' -PstOut 'D:\models\genus_pst.json' -NnueOut 'D:\models\genus_nnue.npy' -Bk 'D:\bk\bratko_kopec.epd' -AuditOut 'D:\results\audit.json'
```

* MON obligatorio 1..4. `--mon` y `--help` se aceptan como nombres de parametros en PowerShell; la sintaxis convencional es `-Mon` / `-Help`.
* Etapa 1: `genSample.py --in InputDb --out SampleDb --sample Sample`.
* Etapa 2: `genPST.py --in SampleDb --out PstOut --poblacion Population --generaciones Generations`.
* Etapa 3: `genNNUE.py --in SampleDb --out NnueOut --poblacion Population --generaciones Generations`.
* Etapa 4: `genAudit.py --pst PstOut --nnue NnueOut --bk Bk --out AuditOut`.
* Las etapas anteriores al MON inicial no se ejecutan; se incrementa MON en memoria tras cada exito.
* Si hay un error, el script termina; se debe volver a ejecutar indicando el MON del paso fallido. MON no se guarda en disco.
* Los archivos de salida son destructivos conforme al comportamiento original de los programas Python.
* Las rutas relativas se resuelven desde el directorio del script. Los directorios destino deben existir.
* El archivo es ASCII sin BOM para evitar errores de parseo en Windows PowerShell.

## Defaults

| Parametro | Default |
|---|---|
| InputDb | `C:\Data\sample_history.pb` |
| SampleDb | `C:\Data\genus.pb` |
| PstOut | `..\..\assets\genus_pst.json` |
| NnueOut | `..\..\assets\genus_nnue.npy` |
| Bk | `C:\Data\bratko_kopec.epd` |
| AuditOut | `..\..\assets\audit.json` |
| Sample | 1000 |
| Population | 100 |
| Generations | 500 |
| Python | python |

No se cambio el algoritmo de ninguno de los cuatro programas ni el numero de muestras usado por el script adjunto.
