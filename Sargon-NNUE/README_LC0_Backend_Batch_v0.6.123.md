# Sargon-NNUE v0.6.123: contrato Backend.evaluate de LC0

## Evidencia

En Windows, el backend `eigen` inicializa pero el módulo de bindings informa:

`TypeError: evaluate(): incompatible function arguments. Expected collections.abc.Sequence[lczero.backends.Input]`

El puente neuronal suministraba un objeto `Input` individual, mientras que los bindings instalados exigen una secuencia.

## Cambio único de producción

`src/sargon_nnue/evaluators/lc0.py`, método `evaluate_pv`:

Antes:

```python
result = self._backend.evaluate(gs.as_input(self._backend))[0]
```

Después:

```python
result = self._backend.evaluate([gs.as_input(self._backend)])[0]
```

No se modifican los demás evaluadores, AlphaZero-MCTS, el jugador LC0-UCI, los scripts PowerShell, bases SQLite ni el algoritmo de búsqueda.

## Instalación

Extraer este ZIP en la raíz de `Sargon-NNUE`, reemplazando únicamente el archivo Python indicado. Mantiene la corrección de DLL de v0.6.122.

## Verificación local en Windows

```powershell
.\scripts\sargon_lc0_probe.ps1 --lc0-weights "data\lc0\model.pb.gz" --lc0-backend eigen
```

La prueba incluida usa dobles de prueba y verifica el contrato de un lote de un elemento y la reconstrucción WDL. La inferencia real debe verificarse en el equipo que tiene LC0 instalado.
