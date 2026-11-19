# picoBit v0.1.33 — Telemetría solicitada

Sólo cambia `train.py`: representación de avance y métricas. Ningún cambio de Sargon, split, selección de datos, calibración, red, pérdida, optimizador o checkpoint.

En cada época se dibujan **tres barras transitorias en el mismo renglón físico**:

- `Epoch(n/N) Train`: pasada de ajuste real; muestra promedio acumulado de predicciones **antes** de cada actualización del optimizador, exactamente sobre los ejemplos usados en los lotes.
- `Epoch(n/N) Verif`: inferencia con los pesos actualizados sobre **todo TRAIN**.
- `Epoch(n/N) Valid`: inferencia con los mismos pesos sobre **todo VALID**, sin actualizaciones de pesos.

Cada barra: porcentaje, procesadas/total, S, S+B, SF, MAE, Sig, ETA.

**Definiciones:** S = media *firmada* en cp de Sargon **calibrado** (`alpha*Sargon+beta`, con clipping); S+B = media firmada en cp de predicción combinada; SF = media firmada en cp de etiqueta Stockfish. No son los MAE individuales. `MAE` = promedio acumulado de `abs((S+B)-SF)` en cp. `Sig` = BCE sigmoide sobre etiquetas residuales continuas; suma ponderada por posición (no media simple de las medias de lote).

Al finalizar cada etapa el progreso de 100% se muestra fugazmente; **se sobrescribe**, y no genera salto de línea. Una sola línea permanente por época comienza con `Epoch best=`. La elección de `best` **sigue siendo `validSig`**, como en v0.1.32; cambiar ese criterio necesitará una decisión separada.

Las medidas de entrenamiento antes del paso del optimizador no coinciden necesariamente con las de `Verif`, que se calculan con los pesos al final de la época. `Epoch best` refiere a la mejor época según validSig, no según MAE.
