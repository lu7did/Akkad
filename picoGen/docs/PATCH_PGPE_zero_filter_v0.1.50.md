# picoGen PGPE v0.1.50 — Excluir etiquetas exactamente cero CP

## Alcance
- PGPE MON 7 excluye `score_white_cp == 0` **antes** de selección por reservorio, tanto T79 como T77.
- Cuenta `excluded_zero` explícitamente y registra estadísticas en los checkpoints.
- MON 8 usa `--exclude-zero` en su muestreo de T79/T77 para comparar PST, NNUE y constantes sobre las **mismas posiciones no-cero**.
- Los CSV originales no se modifican. El entrenador PST MON 6 permanece intacto (su optimización histórica usa su dataset anterior); su evaluación MON 8 sí cambia de muestra.
- `gen_csv_dataset.py` conserva su comportamiento legacy por defecto; la exclusión es opt-in.
- Checkpoints PGPE `v3`: nunca mezclar con `v2` porque cambia el conjunto de entrenamiento. MON 7 explícito archiva antes de reentrenar.
- Evaluaciones 0 CP pueden ser legítimas; este es un filtro experimental solicitado, no un diagnóstico de corrupción.

## Ejecución
Desde `picoGen/tools/train`: `./run_genesis_binpack.ps1 --mon 7 --generations 100`.

## Compatibilidad
No cambia la arquitectura 768x16x1, activation clip(0,1), función objetivo probabilística, output_gene_scale_cp=400, exportación de pesos ni Nurse.
