# Sargon-NNUE v0.6.139 — Corrección de selección del evaluador AlphaZero

## Defecto reproducible

En la versión v0.6.138 `build_engine()` sustituía **siempre** `evaluator=znpz` o `evaluator=zclassic` por `evaluator=lc0`, aun cuando el brain especificaba claramente otro evaluador. El listener fallaba durante la inicialización del motor (antes de emitir `uciok`), y MATCH informaba `motor A cerró salida esperando uciok`.

## Solución (único cambio funcional)

En `src/sargon_nnue/factory.py`, cambiar:

```python
    requested_evaluator = "lc0"
```

por:

```python
    if requested_evaluator is None:
        requested_evaluator = "lc0"
```

La condición se aplica **solo** dentro de `if player_kind == "alphazero":`. De este modo el LC0 sigue siendo el valor por defecto para AlphaZero, pero `znpz` y `zclassic` explícitos se respetan.

No se modifica el algoritmo MCTS, las simulaciones, PUCT, el evaluador NPZ, la política Softmax ni la interface UCI. Los únicos otros cambios son las versiones anunciadas para paquete y MATCH.

## Instalación

Extraer el ZIP sobre la raíz de Sargon-NNUE, conservando la jerarquía `src/` y `tests/`. Requiere los archivos de v0.6.138 previamente instalados (sobre todo `evaluators/zpolicy.py`).

## Pruebas con el entorno ufasta

Desde la raíz del repositorio:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
& 'C:\Users\pedro\ufasta\Scripts\python.exe' -m unittest discover -s tests -p 'test_az_factory_evaluator_v06139.py' -v
& 'C:\Users\pedro\ufasta\Scripts\python.exe' -m unittest discover -s tests -p 'test_zpolicy_v06138.py' -v
```

Probar luego los brains explícitos de `brains.json` en `sargon_match.ps1`, con una muestra corta primero. Si sigue fallando el UCI, consultar `sargon_match.a.log` para distinguir una ruta NPZ inválida, un checkpoint corrupto u otro problema de inicialización.

## Archivos incluidos

- `src/sargon_nnue/factory.py` (bug real)
- `src/sargon_nnue/__init__.py` (versión 0.6.139)
- `src/sargon_nnue/sargon_match.py` (telemetría 0.6.139)
- `tests/test_az_factory_evaluator_v06139.py` (regresión)
