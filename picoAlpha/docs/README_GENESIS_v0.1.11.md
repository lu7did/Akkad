# picoAlpha Genesis v0.1.11 - Correccion de parseo PowerShell

Corrige la cabecera corrupta reportada ` $ï»¿# ` del archivo `run_genesis.ps1`.
El script ahora comienza con `#` (ASCII, sin BOM), de manera que PowerShell 5.1
no puede interpretar accidentalmente el BOM UTF-8 como caracteres `ï»¿`.
El simbolo de telemetria se construye por codigo Unicode en tiempo de ejecucion.

## Control explicito

Tras validar el parametro `-Mon` obligatorio:

```powershell
$MON = [int]$Mon
$RESUME_ENABLED = [bool]$Resume
```

El script imprime al iniciar `Genesis starting MON=3 RESUME=True` cuando se
invoca con `-Mon 3 -Resume`.

## Continuar la evaluacion sin perder resultados

```powershell
.\run_genesis.ps1 -Mon 3 -Resume
```

Alternativamente `--mon 3 --resume` si la version de PowerShell admite los
alias de doble guion existentes.

`-Resume` se pasa literalmente como `--resume` a `teacher.py`.
Con `-Mon 3` los pasos 0, 1 y 2 no se ejecutan.
Con `-Mon 3` sin `-Resume` se imprime una advertencia: no se activa la
reanudacion automaticamente.

No se modifico `teacher.py` ni el mecanismo de checkpoints v0.1.10.
