# picoGen v0.1.53 — Corrección EvoTorch ReadOnlyTensor

**Base requerida:** parche v0.1.52 aplicado en la raíz `akkad`.

## Defecto reproducido

En `genGrumpyPGPE.py`, el objetivo vectorizado de EvoTorch recibe un
`ReadOnlyTensor`. `params.to(device)` puede preservar la subclase de solo lectura.
La acumulación `sum_loss += ...` invoca una modificación in situ y termina en:

`TypeError: The contents of a ReadOnlyTensor cannot be modified`

La excepción ocurre en la primera generación, antes de completar una iteración.

## Corrección

- En `fitness_population`, desacoplar el tensor del tipo de solo lectura mediante
  `params.detach().clone().as_subclass(torch.Tensor).to(device=device,dtype=torch.float32)`.
- Acumular usando `sum_loss = sum_loss + ...` (sin modificación in situ).
- Nueva prueba de regresión con una subclase de tensor que rechaza `__iadd__`,
  más comprobación del fitness frente a una evaluación individual de referencia.

**Sin cambios** en los 1680 coeficientes, la función de pérdida mixta, la
optimización híbrida PGPE+Adam, T79/T77, el formato de checkpoint, las 100
generaciones ni la población de 50 individuos.

## Ejecución

Desde `picoGen/tools/train`:

```powershell
.\run_genesis_binpack.ps1 --mon 7 --generations 100
```

El fallo previo se produjo antes de producir una generación válida, así que la
corrida debe iniciarse nuevamente desde generación 1. **No hay que regenerar los CSV**.

## Verificación

`python -m unittest -v test_grumpy_pgpe` — cinco pruebas exitosas en CPU.
La corrida completa en Intel XPU / EvoTorch 0.6.1 aún debe comprobarse en el
entorno Windows del proyecto. Este parche corrige la excepción reportada, pero
no afirma haber completado ese entrenamiento.
