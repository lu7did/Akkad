# Sargon-NNUE v0.6.82 — Emoji UTF-8 en Brainmaker

Reemplazar solo `scripts/sargon_brainmaker.ps1`.

Corrección: al invocar Python desde Windows PowerShell, fuerza PYTHONIOENCODING=UTF-8, PYTHONUTF8=1 y la codificación de salida de consola a UTF-8, restaurando las configuraciones al salir.

No cambia sargon_brainmaker.py, brains.py, resultados Elo ni JSON.

Ejemplo desde scripts:
```
.\sargon_brainmaker.ps1 --elo --brains ..\data\brains\brains.json --elo-reference classic --elo-score 1000 --rally ..\data\rally\mdqopen.json
```

Si los caracteres siguen dañados incluso ejecutando Python sin PowerShell, revisar fuente de terminal y configuración del host; el parche no puede garantizar soporte glífico del emulador de terminal.
