# picoBit train.py v0.1.35 — parámetro --lrmin

Modificación exclusiva: incorpora `--lrmin` (por defecto `0.0`) al planificador `torch.optim.lr_scheduler.CosineAnnealingLR`, mediante `eta_min=args.lrmin`.

Verifica `0 <= --lrmin <= --lr` y `--lr > 0`. Registra ambos valores al iniciar y agrega `lrmin` al manifiesto de hiperparámetros.

Ejemplo: `python train.py --in sample_history.pb --sample 10000 --validation 20 --epoch 50 --lr 0.001 --lrmin 0.00001`

No altera Sargon, partición de datos, pérdida, arquitectura, entrenamiento, validación ni telemetría de barras.
