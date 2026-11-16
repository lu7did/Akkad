# picoGenus PST v0.1.20 — diagnóstico de acuerdo con el maestro sin Stockfish

- El único objetivo genético continúa siendo el MSE/RMSE de evaluación de la posición en centipeones de blancas, basado en `teacher_cp`, `teacher_mate` o `teacher_value` de la base `.pb`.
- No se importa ni ejecuta `chess.engine` para efectuar análisis externos. Solo se usa `python-chess` para legalidad y análisis de jugadas de un ply.
- Al finalizar cada generación se obtiene la **mejor mutación de esa generación por MSE** y se evalúa qué jugada elegiría en cada FEN con `teacher_uci` legal de la base. Blancas maximizan y negras minimizan la puntuación local de las posiciones hijas.
- Los resultados aparecen como `agreement=X/Y (Z%)` en la telemetría y en `diagnostics` dentro de cada checkpoint `.genNNNNN.json`, con `move_agreement_correct`, `move_agreement_total`, `move_agreement_skipped`, `move_agreement_pct`.
- Sin `teacher_uci` utilizable se imprime `agreement=N/A`. Las posiciones inválidas o sin jugada legal de referencia no se puntúan como desaciertos.
- El diagnóstico no altera el fitness, la población, el criterio `best`, la mutación, la semilla, `--resume`, ni el contenido de `PST_best.json`. Se conserva el hash de posiciones y puntuaciones para poder reanudar checkpoints anteriores.
- No puede computarse la pérdida real en centipeones de una jugada alternativa sin disponer de la evaluación de esa alternativa; **no se generan valores ficticios ni se invoca Stockfish**.
- Se conservan los operadores y redondeos actuales de Sargon III v0.1.19. El diagnóstico se computa solamente una vez por generación para no multiplicar el coste por el tamaño de la población.

## Uso

```powershell
python .\genPST.py --in "C:\ruta\base.pb" --out "C:\ruta\genus_pst.json" --poblacion 100 --generaciones 100
```

La dependencia `python-chess` es necesaria para la ejecución real. Los tests unitarios sin ella solo verifican la lógica de control, persistencia y agregación; no reemplazan una corrida de validación con posiciones reales.
