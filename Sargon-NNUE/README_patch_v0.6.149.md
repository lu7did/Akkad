# Sargon-NNUE v0.6.149 — `--level` y brainid no registrados

Se modifica solo el comportamiento de `--level`: los encuentros donde **al menos uno** de los brainid del Rally no figura en `brains.json` se ignoran completamente (sin modificar Elo de ninguno de los contrincantes). Se contabilizan como `brainid no registrados excluidos` en el resumen.

Los perfiles definidos en `brains.json` pero sin `rating_elo` continúan partiendo de Elo **400**. Sin `--save` no se altera el archivo. Con `--save`, solo se actualizan perfiles existentes. Si no hay ningún encuentro puntuable entre dos perfiles registrados, se informa una condición de error sin escribir cambios.

Ejemplo: `python -m sargon_nnue.sargon_brainmaker --level --brain data/brains/brains.json --rally data/rally/rally.json --save`

Parche incremental sobre v0.6.148.
