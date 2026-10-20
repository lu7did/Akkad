# Auditoría de `.pb` v0.6.35
Desde el directorio scripts, con el paquete instalado en `src`:

```powershell
C:\Users\pedro\ufasta\Scripts\python.exe -m sargon_nnue.sargon_audit_pb --input "..\data\pb\boot.pb" --validation 5 --seed 42 --out "..\data\pb\audit.json"
```

Para añadir métricas de un checkpoint:

```powershell
C:\Users\pedro\ufasta\Scripts\python.exe -m sargon_nnue.sargon_audit_pb --input "..\data\pb\boot.pb" --network "..\data\nnue\torch034\nnue_epoch_002.npz" --validation 5 --seed 42 --out "..\data\pb\audit_epoch_002.json" --csv "..\data\pb\audit_epoch_002.csv"
```

Requiere NumPy. No requiere PyTorch ni Stockfish. `--validation` recrea una partición determinista mediante NumPy PCG64; para comparación exacta con el entrenador, verificar que su algoritmo de partición coincida. La detección de duplicados utiliza la codificación de características y el contador halfmove; distintas historias pueden compartir esa codificación. La etapa de apertura/medio juego/final es una heurística y se proveen además cubetas continuas por fase y ply. Los promedios son por posición, no por partida.
