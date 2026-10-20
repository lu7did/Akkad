SARGON BRAINMAKER v0.6.66 - Presentación --list

Reemplazar src/sargon_nnue/sargon_brainmaker.py. No cambiar el PS1.
Ejecutar desde scripts:
  .\sargon_brainmaker.ps1 --brain ..\data\brains\brains.json --list

Las estadísticas games, win, draw y loss son opcionales: si no están definidas se muestra un guion (—), nunca se inventan valores. La modificación no actualiza las estadísticas ni modifica brains.json. No cambia el esquema ni el motor.

Si se añaden estos campos manualmente al JSON, la validación del motor actual (brains.py) los rechaza como parametros desconocidos; por ello NO se recomienda agregarlos al perfil de motor. Hasta integrar un registro de resultados, las estadísticas aparecerán como —.
