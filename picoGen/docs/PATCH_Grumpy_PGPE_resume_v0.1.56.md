# picoGen v0.1.56 — reanudación de Grumpy PGPE hasta G300

## Instalación
Aplicar el ZIP incremental sobre Akkad v0.1.55 desde la raíz del repositorio, sin modificar datasets ni cambiar el RunId.

## Comando (desde picoGen/tools/train, Windows PowerShell)

```powershell
.\run_genesis_binpack.ps1 --mon 7 --generations 300 --resume-nnue
```

`--generations 300` significa **300 generaciones en total**, no 300 adicionales. Si el checkpoint corresponde a G100, se intentará ejecutar de G101 a G300 (200 generaciones nuevas), con 50 participantes PGPE, 800.000 posiciones en pool y lotes de 40.000, conservando el objetivo CP_MSE y evaluación T77 completa.

**Obligatorio:** `picoGen/assets/binpack-grumpy-pgpe-fp32-001/nnue/best.grumpy-pgpe-v3.latest.pt` completo. `best.npy` es solo el modelo exportado y no puede restaurar el estado del optimizador.

## Protección de continuidad
- `--resume-nnue` requiere explícitamente `--mon 7` y `--generations TOTAL`.
- En vez de archivar `nnue`, conserva el checkpoint y el mejor modelo. Verifica que hay resumen de generación anterior y que el objetivo nuevo es mayor.
- Solo se permite aumentar el **total** de generaciones; población, semillas, datos, muestreo, dispositivo y demás variables bloqueadas no pueden alterarse mediante esta opción.
- El entrenador valida que `format` e `identity` del checkpoint coinciden antes de actualizar pesos; preserva `best`, `Adam`, distribución/optimizador PGPE y estados RNG serializados de la versión anterior.
- El checkpoint se escribe por reemplazo atómico cada generación. Se reportan hitos G125, G150, etc. MON 8 vuelve a auditar después de completar.

## Límites de verificación
- Se ejecutaron nueve pruebas unitarias CPU, sintaxis Python y validación ZIP.
- No fue posible ejecutar EvoTorch 0.6.1 ni Intel XPU en el entorno de desarrollo. La reanudación a partir del checkpoint real G100 no se ha verificado en Windows.
- Los checkpoints v0.1.55 serializan el estado aleatorio de PyTorch CPU y el RNG de NumPy del entrenador, pero no documentan de forma explícita el RNG interno independiente del problema EvoTorch ni el RNG Intel XPU. Por tanto, **se recuperan los parámetros y estados almacenados**, pero no se garantiza identidad bit a bit con una corrida ininterrumpida.
- Antes de ejecutar el comando, aconsejamos guardar una copia externa del archivo `.latest.pt`. No se regeneran los CSV T79/T77.
