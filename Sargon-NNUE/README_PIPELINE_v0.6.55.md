# Pipeline v0.6.55

`./scripts/sargon_pipeline.ps1` encadena:
1. `sargon_prepare` del `boot.pb` con `--resample` y nueva semilla (por defecto 10%, seed 314159).
2. Etiquetas `--classic` en una copia al 100%.
3. Etiquetas `--stockfish` en otra copia al 100%, preservando `classic_cp`.
4. `sargon_audit --target classic` sobre la base.
5. `sargon_train` CLASSIC durante 10 epochs usando `--scheduler plateau` y `--save-best`.
6. Auditoría del mejor checkpoint CLASSIC.
7. Fine-tune Stockfish desde ese checkpoint con `--shuffle 20 --refine-stockfish-max-cp 10` durante tres epochs.
8. Auditorías finales de ajuste CLASSIC y Stockfish sobre el checkpoint refinado.

Desde la carpeta scripts de Windows:

```powershell
.\sargon_pipeline.ps1 -InputPb '..\data\pb\boot.pb' -WorkDir '..\data\runs\experimento_01' -Resample 10 -Seed 314159 -StockfishPath 'C:\Users\pedro\github\bobby\stockfish\stockfish.exe'
```

El directorio de salida debe ser nuevo: no sobrescribe checkpoints ni bases antiguas. El etiquetado Stockfish puede requerir mucho tiempo; su profundidad es configurable.

AUDIT v0.6.55 añade `--target classic|stockfish|pgn`, calcula RMSE CLASSIC en centipawns, y omite etiquetas terminales de ese objetivo. `--target stockfish` con checkpoint CLASSIC mide error de expectativa WDL utilizando `sigmoid(raw)`; esto es una medida auxiliar y no prueba fuerza de juego.

**Limitaciones**: sin prueba integral de PowerShell/Intel XPU en este entorno. No ejecuta MATCH/JUDGE sin especificar brains y jugadores.
