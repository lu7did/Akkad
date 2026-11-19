# picoBit NNUE FP32 v0.1.39 — Alineación matemática MAE

Base incremental: `akkad_picoBit_nnue_fp32_patch_v0.1.38.zip`. Aplicar desde la raíz de `akkad`.

## Cambios estrictamente solicitados

1. **Objetivo TRAIN:** `torch.nn.functional.l1_loss(predicted_residual_cp, target_residual_cp)` en centipeones. `S_cal + pred_residual` se compara conceptualmente con Stockfish con el mismo recorte de referencia.
2. **Objetivo residual:** `clip(Stockfish,-C,C) - clip(alpha*Sargon+beta,-C,C)`; no se vuelve a recortar la resta. Con `C=1500`, el residuo puede estar entre -3000 y +3000 cp.
3. **Checkpoint:** `best.pt` se reemplaza sólo si el MAE de `VALID_S+B` mejora, nunca según la pérdida sigmoide. Contiene `validation_combined_mae_cp` y `selection_criterion`.
4. **Sig:** permanece en Train, Verif, Valid y en `history.jsonl` como estadístico diagnóstico histórico, **NO** como loss optimizada o criterio de checkpoint. `--sigmoid-temperature` queda por compatibilidad y afecta únicamente ese indicador.
5. **Telemetría:** se preservan las tres barras de progreso por época, sus métricas, la consola de ancho dinámico y el resumen `Epoch best`, ahora con `bestMAE` en cp.

## Sin modificaciones

Arquitectura FP32 781-64-64-1, ClippedReLU [0,1], BatchNorm, AdamW, scheduler coseno, `--lr`, `--lrmin`, split TRAIN/VALID, filtro quiet, calibración Sargon, `sargon.py`, `export.py`, `audit.py`, formatos de checkpoint y manifest existentes. Las claves nuevas son aditivas; el formato de checkpoint `picobit-residual-nnue-fp32-v1` se conserva.

## Verificación

- Compilación sintáctica Python.
- Prueba numérica de igualdad MAE(residuo) = MAE(Sargon+NNUE−Stockfish) con residuo de magnitud >1500 cp.
- PyTorch: propagación hacia adelante, backward, actualización y self-test.
- Sin ejecución de dataset SQLite real: `python-chess` no se encuentra instalado en el ambiente de verificación.

Nota: optimizar MAE **no garantiza** reducir el sobreajuste; elimina una desalineación comprobada entre objetivo, medición y selección de checkpoint.
