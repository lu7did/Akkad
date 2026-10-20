# Auditoría Sargon PB v0.6.36

Parche sobre v0.6.35: sustituir `src/sargon_nnue/sargon_audit_pb.py` y `src/sargon-audit-pb.py`.

- Conserva controles estructurales, estadísticas de duplicados y MSE de la red por fase, valor de material, ply y resultado.
- **Nuevo:** `segment_baselines` en JSON y filas `baseline` en CSV. Para cada segmento (etapa, fase material o rango de 20 plies), predice la media del resultado **exclusivamente del conjunto de entrenamiento**, y mide MSE en ambas particiones. Si un segmento no aparece en entrenamiento, utiliza la media global de entrenamiento.
- **Nuevo:** `calibration` en JSON y filas `calibration` en CSV: compara la predicción media y el resultado medio por intervalos de predicción, en entrenamiento y validación.
- `--calibration-bins N` (predeterminado 10, de 2 a 100).
- `--network` sigue siendo obligatorio para obtener las métricas de calibración; el análisis de dataset y las baselines se calculan sin red.
- La auditoría no cambia el dataset, checkpoint ni entrenador. `--max-positions` produce estadísticas **parciales**; para comparar modelos debe omitirse.

Ejemplo desde `scripts`:

```powershell
C:\Users\pedro\ufasta\Scripts\python.exe -m sargon_nnue.sargon_audit_pb `
  --input "..\data\pb\boot.pb" `
  --network "..\data\nnue\torch034\nnue_epoch_002.npz" `
  --validation 5 --seed 42 --calibration-bins 10 `
  --out "..\data\pb\audit_epoch_002_v0636.json" `
  --csv "..\data\pb\audit_epoch_002_v0636.csv"
```

**Interpretación:** un baseline por grupo puede ser mejor que el promedio global sin conocer ajedrez, por eso es un control útil. Los rangos definidos por material y ply son heurísticos y no equivalen a una evaluación de calidad ajedrecística. Un MSE más bajo en un segmento no implica mejor capacidad ajedrecística.
