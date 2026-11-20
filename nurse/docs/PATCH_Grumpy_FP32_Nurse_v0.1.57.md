# Akkad v0.1.57 — Nurse compatible con picoGen Grumpy PGPE FP32

## Aplicación
ZIP incremental desde raíz de `akkad`, posterior a v0.1.56. Solo modifica el cargador `genus-nnue` de Nurse; no modifica entrenador ni otros evaluadores.

## Configuración para probar G298
En la configuración de Nurse usar `evaluator=genus-nnue` y `evaluator.network` apuntando a:

`picoGen/assets/binpack-grumpy-pgpe-fp32-001/nnue/best.npy`

Usar los pesos del run G298 **del equipo de entrenamiento** (no la copia G100 anterior). Mantener `best.active.json` en el mismo directorio. El cargador lo exige para identificar Grumpy FP32; no inferirá el tipo únicamente por longitud.

## Semántica
- 1.680 coeficientes FP32 ordenados: factores `[192,8]`, sesgos `[8]`, salida `[8,16]`, sesgos de bucket `[8]`.
- Dos perspectivas con intercambio STM, 8 buckets por cantidad de piezas, Clipped ReLU `[0,32]`.
- Material blanco fijo `(100,300,300,500,900,0)`; residuo NNUE escalado `400/1024` desde perspectiva STM, resultado final en centipeones blancos.
- Infiere con NumPy, sin Torch ni importar el proyecto picoGen al ejecutar Nurse.
- Falla explícitamente ante manifiesto erróneo, pesos de otra forma/dtype, NaN o Inf. Conserva la compatibilidad previa de `genus-nnue`.

## Comprobación rápida desde raíz de akkád

```powershell
$env:PYTHONPATH = (Resolve-Path .\nurse\src).Path
python -m nurse.evaluators.npz --version
```

La comprobación de partida debe hacerse con el evaluador `genus-nnue`, **no** con `grumpy` (éste requiere el binario GRMP0001 cuantizado), ni con `npz` (otra arquitectura).

## Limitación
El modelo G298 no estaba adjunto en esta conversación; se verificó con pesos de G100 (mismo formato). La comparación del modelo G298 con el entrenador debe ejecutarse en el equipo del usuario.
