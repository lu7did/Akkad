# Sargon-NNUE v0.6.124 — Corrección del contrato LC0 `Output.p_softmax`

## Defecto reproducido

La prueba real de `sargon_lc0_probe.ps1` usando `--lc0-backend eigen` inicializó correctamente la red y devolvió un objeto `Output`, pero falló con:

```
TypeError: p_softmax(): incompatible function arguments.
Expected: p_softmax(self, samples: collections.abc.Sequence[typing.SupportsInt | typing.SupportsIndex])
```

La versión v0.6.123 suministraba índices separados como argumentos posicionales (`*indices`).

## Cambio en el código de producción

Se modifica **una única expresión** del método `LC0Evaluator.evaluate_pv()` en `src/sargon_nnue/evaluators/lc0.py`:

```python
# Anterior (incorrecto):
scores = [float(v) for v in result.p_softmax(*indices)]
# Correcto:
scores = [float(v) for v in result.p_softmax(indices)]
```

El archivo incluido conserva los cambios ya aplicados en v0.6.122 (búsqueda de DLL en Windows) y v0.6.123 (`Backend.evaluate([Input])`). No se altera ningún otro módulo de Sargon-NNUE.

## Instalación

Descomprimir en la **raíz del proyecto** y sobrescribir únicamente `src/sargon_nnue/evaluators/lc0.py`. El script de prueba incluido se instala en `tests/`.

## Prueba

```powershell
.\scripts\sargon_lc0_probe.ps1 `
    --lc0-weights "data\lc0\model.pb.gz" `
    --lc0-backend eigen
```

La prueba unitaria incluida verifica los dos contratos de argumentos con objetos simulados. No se realizó inferencia real con el backend ni validación de las probabilidades de salida en este entorno.
