# genAudit.py — evaluación en VALIDATION etiquetada (v0.1.34)

Entrada: `--database` (alias `--db`) apunta a la base SQLite etiquetada con Stockfish que se utilizó para entrenar PST y NNUE; `--pst` y `--nnue` apuntan a los modelos generados. Modo predeterminado: `--mode validation`.

El auditor recupera el conjunto VALIDATION utilizando `gen_dataset_split.load_split()`, compartido con `genPST.py` y `genNNUE.py`: partición por partidas, semilla 42, `--max-positions` y `--validation-sample 20`. Las tres evaluaciones PST, NNUE y CLASSIC se comparan individualmente contra `teacher_cp` convertido a POV blanco; no se ejecuta Stockfish ni se compara par a par contra CLASSIC.

Ejemplo Windows (desde `picoGenus/tools/train`):

```powershell
python .\genAudit.py --database C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\genus.pb --pst ..\..\assets\genus_pst.json --nnue ..\..\assets\genus_nnue.npy --seed 42 --max-positions 0 --validation-sample 20 --out ..\..\data\audit_validation.json
```

**Importante:** `--max-positions` debe coincidir con el entrenamiento: para la sesión descrita, hay 9.972 posiciones seleccionadas, por lo que si la base contiene esas 10.000 muestras se usa `0` (todas), no `9972`. El hash de split esperado en esa sesión es `8b20b904235bf824f44b2e8baa681ba7a49cd4dcad0c07200267036b5418a8a7`; usar `--expected-split` para verificarlo.

El auditor registra por posición ID, game_id, FEN, referencia Stockfish, predicción, error con signo y absoluto; resume cada motor con MAE, RMSE y sesgo, y ordena por MAE y RMSE. Esto es VALIDATION usado para seleccionar modelos, no TEST independiente.
