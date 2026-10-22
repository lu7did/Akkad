# Sargon-NNUE v0.6.172 — TinyGyal policy promotion mapping

Parche incremental **sobre v0.6.171**. No modifica AlphaZero, LC0, arquitectura neuronal ni entrada histórica.

## Corrección

Para promoción vertical `a7a8` en la política convolucional oficial LC0:

- `a7a8n` — canal 0 (ray normal hacia adelante, **caballo**)
- `a7a8r` — canal 67
- `a7a8b` — canal 68
- `a7a8q` — canal 69 (**dama**)

La implementación anterior asignaba erróneamente dama al ray normal y caballo al canal 69. Esta versión aplica los canales especiales a R/B/Q; N emplea el desplazamiento ordinario. Enroques no cambian.

## Verificaciones

1. `python scripts/test_tinygyal_policy_special.py`
2. `scripts/run_test_tinyGyal.ps1` (o ejecutarlo desde la carpeta scripts).

Se espera **9/9 PASS**, pero la prueba de paridad completa requiere el entorno local con `python-chess` y la referencia LC0/Eigen. No afirmamos haberla ejecutado aquí.

`history=INCOMPLETE` es información sobre ausencia del historial anterior en un FEN aislado; no es un fallo de la prueba. `PASS` indica conformidad numérica. 
