# Sargon-NNUE v0.6.161 — Match reconoce Doc / Grumpy

Parche incremental sobre v0.6.160.

- `sargon_match.py`: las opciones `--a-player`, `--b-player`, `--a-evaluator` y `--b-evaluator` toman sus valores permitidos de `brains.py` (`PLAYER_CHOICES` / `EVALUATOR_CHOICES`).
- Permite `player=doc` y `evaluator=grumpy` en `--brain ... --idA dwarf --idB ...`.
- `__init__.py`: versión 0.6.161.
- No se modifican algoritmos de búsqueda, evaluación ni configuración de brains.

## Prueba propuesta

```powershell
python -m sargon_nnue.sargon_match --brain data\brains\brains.json --idA dwarf --idB aegir --pairs 1 --max-plies 20
```

Validación realizada: compilación sintáctica y verificación de valores permitidos; no se ejecutó Match completo por falta de `python-chess` en el entorno de generación.
