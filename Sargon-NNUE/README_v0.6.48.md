# Sargon-NNUE 0.6.48: CLASSIC teacher (prototipo de integración)

## Instalación
Aplicar sobre el proyecto con los parches anteriores hasta v0.6.47. Reemplazar únicamente los archivos incluidos. `sargon_prepare.py` mantiene `--resample` y `--stockfish`; MATCH conserva auditoría Stockfish.

## Generar datos CLASSIC en un .pb NUEVO
Desde un `.pb` existente (sin alterar el original):

```powershell
python -m sargon_nnue.sargon_prepare --input "..\data\pb\boot_sf_10pct.pb" --resample 100 --seed 42 --classic --out "..\data\pb\boot_classic.pb"
```

También es posible preparar directamente desde PGN con `--dir "..\data\*.pgn" --out ... --classic`. La columna `classic_cp` es cp orientados a blancas y no modifica la WDL original. El muestreo con `--resample` conserva etiquetas CLASSIC cuando ya existen.

## Entrenamiento

```powershell
python -m sargon_nnue.sargon_train --input "..\data\pb\boot_classic.pb" --nnuedir "..\data\nnue\classic" --pytorch --device xpu --torch-foreach off --torch-dtype float64 --optimizer adamw --lr 0.0001 --batch-size 64 --epoch 10 --validation 5 --seed 42 --classic --weight-classic 1
```

Solo está habilitado CLASSIC con backend PyTorch en esta versión; NumPy rechaza la opción explícitamente. `--shuffle` se mantiene. El modo CLASSIC usa salida lineal raw y objetivo `classic_cp/400`; un NPZ de esa ejecución usa exactamente `round(raw*400)` (con conversión de salida actual del evaluador a entero truncado), coincidente en signo y escala con `NpzEvaluator.evaluate` del listener. La pérdida en consola es MSE en unidades `(cp/400)^2`; para convertir RMSE a cp multiplicar por 400. Mezcla CLASSIC+PGN admitida cuando `0<--weight-classic<1`: se mapea PGN a [-1,1]. No se admite mezclar simultáneamente Stockfish y CLASSIC en este prototipo.

## MATCH sin aperturas forzadas

```powershell
python -m sargon_nnue.sargon_match --a-player sargon-plus --a-evaluator classic --b-player sargon-plus --b-evaluator npz --b-network "..\data\nnue\classic\nnue_epoch_003.npz" --pairs 15 --csv "..\data\classic_match.csv" --pgn "..\data\classic_match.pgn" --audit-classic --audit-csv "..\data\classic_positions.csv"
```

Por defecto todas las partidas empiezan desde `startpos`; `--opening` sigue disponible solo de forma explícita. La auditoría CLASSIC compara por posición y por alternativas legales estáticas; no cambia decisiones del jugador. Registra posiciones no terminales luego de cada ply. Para Top-1, el empate se resuelve por orden UCI; regret es la diferencia entre máxima valoración CLASSIC y la valoración CLASSIC de la jugada favorita de la red, desde el turno correspondiente.

## JUDGE

```powershell
python -m sargon_nnue.sargon_judge --input "..\data\classic_match.csv" --positions "..\data\classic_positions.csv"
```

Informes de MAE, RMSE, sesgo, acuerdo Top-1, regret por fase y máximos errores. Conserva lectura de CSV WDL anteriores.

## Limitaciones y comprobaciones pendientes

- Las puntuaciones especiales de mate (±100.000 cp) se conservan en `.pb` para fidelidad, pero se **excluyen de TRAIN y VALIDATION numéricos** por no ser evaluaciones posicionales; el motor continúa resolviendo finales según sus reglas. Los empates con score 0 quedan en los datos.
- Una base `.pb` codifica características de tablero, pero no historial completo de repeticiones: al reconstruir desde `.pb`, la evaluación exacta de `claim_draw=True` puede diferir si la posición dependía de una repetición previa. Para identidad estricta deben cotejarse FEN, reglas de juego e historia de repeticiones.
- Verificado `compileall` y JUDGE con CSV sintético. No se pudo ejecutar motor/PGN completo aquí: falta python-chess en este runtime. Validar primero con `--resample 1` y pocas partidas en el entorno del proyecto.
