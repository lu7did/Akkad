# picoGen Grumpy PGPE v0.1.54 — memoria de Adam en XPU

## Incidencia reproducible

MON 7 de v0.1.53 llega a `adam.step()` y lanza `RuntimeError: level_zero backend failed with error: 39 (UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY)` desde `torch._foreach_lerp_` dentro de `_multi_tensor_adam` en Intel Arc XPU con PyTorch 2.14.0+xpu.

## Corrección (sobre v0.1.53)

- **Sin cambio de arquitectura, dataset, población, generaciones ni pérdida.** Grumpy sigue con 1.680 coeficientes FP32, material fijo y PGPE con ranking centrado.
- El candidato `refined` es ahora un parámetro de **CPU** y `Adam(..., foreach=False)` tiene parámetros, momentos y pasos exclusivamente en CPU.
- Cada paso analítico crea un tensor hoja efímero en el dispositivo de evaluación (XPU, CUDA o CPU), computa allí la derivada de la misma pérdida y transfiere **solo el gradiente de 1.680 flotantes** a CPU. El cálculo y el recorte de gradientes no cambian.
- Las comparaciones con PGPE transfieren el candidato refinado a XPU solo para inferencia y devuelven a CPU los pesos si PGPE gana.
- Checkpoint del entrenador cambiado a `picogen-grumpy-1680-pgpe-hybrid-cp-v2`, `best.grumpy-pgpe-v2.latest.pt`, para impedir reanudar estados antiguos de Adam en XPU. **El contrato del modelo exportado permanece intacto.**
- Se añade prueba de regresión de Adam sobre CPU, además de la de `ReadOnlyTensor`.

## Aplicación y ejecución

Extraer el ZIP en la raíz de `akkad`, sobre v0.1.53. Desde `picoGen/tools/train`:

```powershell
.\run_genesis_binpack.ps1 --mon 7 --generations 100
```

No regenerar CSV. Ejecutar desde generación 1, porque la ejecución fallida no completó ninguna generación. Mantiene 50 individuos, 25 pares simétricos, 100 generaciones y 4 pasos analíticos por generación. El archivo de red final y su manifest no cambian de formato.

## Verificación realizada

Se ejecutaron seis pruebas unitarias en CPU (incluyendo actualización Adam y lectura de parámetros EvoTorch); compilación sintáctica Python y ZIP integridad. **No se dispone de Intel XPU aquí para probar la corrida completa.** Si surge otra excepción en XPU, enviar traza completa. 
