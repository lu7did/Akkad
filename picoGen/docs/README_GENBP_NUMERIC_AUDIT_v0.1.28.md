# picoGenus v0.1.28 — Contrato post-BM de Bratko–Kopec

- `genBP.py` carga el tablero del EPD, aplica la primera solución legal `bm` (si hay varias, preserva todas en `headers_json`), consulta Stockfish **sobre el tablero resultante** y escribe `positions.fen` = FEN posterior, `played_uci` = BM aplicado, `teacher_uci` = recomendación de Stockfish *desde la posición posterior*, `teacher_cp` = puntuación de ese FEN desde la perspectiva del bando al turno **posterior**. `games.start_fen` conserva el FEN original del EPD. Contrato `epd-bm-result-v1` en el JSON de cabecera. Posiciones terminales no llevan centipeones inventados; pueden registrarse con `teacher_cp=NULL` y se excluyen del RMSE.
- `genAudit.py` deja de comparar jugadas; aplica `bm` y verifica que el FEN resultante y `teacher_cp` correspondan a lo almacenado por `genBP.py`. Exige `--db` y rechaza bases etiquetadas con el contrato anterior; calcula RMSE, MAE, sesgo, correlación y tiempo de evaluación para los mismos FEN de PST y NNUE.
- Esta versión **no modifica `genPST.py`, `genNNUE.py`, `teacher.py`, `loader.py` ni `run_genesis.ps1`**. Debido a que `run_genesis.ps1` contiene rutas locales personalizadas, se incluye `enable_numeric_audit.ps1` que cambia *solo* el argumento MON=4 añadiendo `--db $SampleDb` y guarda el script original con extensión `.bak`. Ejecutarlo explícitamente una vez antes de lanzar Genesis.
- IMPORTANTE: el MON=1 de Genesis sobrescribe actualmente la misma ruta `SampleDb` al ejecutar `genSample.py` y luego `genBP.py`; la salida final contiene posiciones Bratko–Kopec, no las 5.000 de muestra. No se modifica ese flujo sin autorización adicional.
- Regenerar la base de 24 con MON=1 antes de auditar; la base generada por genBP antiguo NO es válida para el nuevo modo.

## Uso

```powershell
# Una vez, desde picoGenus/tools/train:
.\enable_numeric_audit.ps1
# Regenerar la base post-bm, entrenar y auditar:
.\run_genesis.ps1 --mon 1
# Alternativa para invocar auditoría directamente:
python .\genAudit.py --pst <PST.json> --nnue <NNUE.npy> --bk <bratko_kopec.epd> --db <Bk.pb> --out <audit.json>
```

**No se garantiza cobertura de 24 referencias cp**: si una BM produce un estado terminal o Stockfish devuelve mate, no existe cp numérico y el caso se excluye del RMSE con aviso.
