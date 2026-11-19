# picoBit v0.1.36 — reparación de telemetría

Partiendo de `train.py` v0.1.35, se restituye el formato solicitado:

- **Epoch(N/M) Train:** barra con avance porcentual, procesadas/total, promedios S/S+B/SF, MAE, Sig y ETA.
- **Epoch(N/M) Verif:** misma barra, evaluando TRAIN luego de actualizar pesos y sin gradientes.
- **Epoch(N/M) Valid:** misma barra para VALID independiente.
- **Epoch best=...:** línea final con MAE de Sargon y Sargon+BNN para TRAIN y VALID, pérdida sigmoide y LR.

Cada barra se actualiza con retorno de carro (`\r`), sin saltos de línea en las actualizaciones; solo se imprime un salto al finalizar **cada etapa**, dejando exactamente tres líneas completas por época, más una línea de resumen.

No se ha modificado selección, arquitectura, evaluador Sargon, calibración, gradientes, loss, optimizador, scheduler ni `--lrmin`. No se modifican `export.py` ni `audit.py`.
