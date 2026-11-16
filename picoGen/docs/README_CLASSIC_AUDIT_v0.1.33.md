# picoGenus — Auditoría contra CLASSIC v0.1.33

## Contrato

`genAudit.py` conserva los argumentos (`--pst`, `--nnue`, `--bk`, `--db`, `--out`) y los FEN *posteriores* a las jugadas `bm` originales del EPD. No selecciona movimientos ni vuelve a consultar Stockfish: utiliza los `teacher_cp` previamente almacenados por `genBP.py`.

Se comparan **tres** evaluadores sobre los mismos FEN, con puntajes en centipeones desde la perspectiva de blancas:

- `PST`: parámetros evolucionados de `genPST.py` (evaluador experimental `gen_sargon_core`).
- `NNUE`: modelo entrenado, usando el mismo cargador actual.
- `CLASSIC`: port literal de la función heurística CLASSIC de `Sargon-NNUE/src/sargon_nnue/evaluators/classic.py` (v0.6.153, portada de Challenger SargonEngine). El módulo `gen_classic_core.py` no invoca ni depende del motor Sargon-NNUE, ni utiliza DEFAULTS experimentales Sargon III. Los métodos de la clase coinciden exactamente con la base autorizada `akkad(20261113-010040).zip`; la prueba AST comprueba dicha identidad.

**Importante:** `CLASSIC` es el evaluador canónico de Akkad portado de Challenger, **no** una reconstrucción históricamente verificada del evaluador interno de Sargon III. Tampoco es el `gen_sargon_core.DEFAULTS` del entrenamiento PST. Por eso las comparaciones son válidas como referencia CLASSIC del proyecto, no como afirmación sobre el Sargon III histórico.

## JSON

Formato actualizado a `picogenus-post-bm-numeric-audit-v3`:

- `methods.PST`, `methods.NNUE` y `methods.CLASSIC`: métricas de error contra la misma etiqueta Stockfish (`rmse_cp`, `mae_cp`, `bias_cp`, correlación, tiempos).
- `versus_classic.PST` y `.NNUE`: distancia al valor CLASSIC (`rmse_to_classic_cp`, `mae_to_classic_cp`, `bias_to_classic_cp`); mejora o deterioro en RMSE frente a Stockfish, con valores absolutos y porcentuales; cantidad de FEN donde cada candidato es mejor o peor que CLASSIC contra Stockfish.
- `cases`: los campos existentes más los casos `predictor=CLASSIC` y para PST/NNUE los campos `classic_value_cp_white`, `difference_to_classic_cp` y `beats_classic_vs_stockfish`.

La comparación directa de errores responde: **¿PST o NNUE se acercan más a Stockfish que CLASSIC?** La distancia entre predicciones responde una pregunta diferente: **¿cuánto se alejan del comportamiento CLASSIC?** No confundir ambas.

## Uso

Con los argumentos actuales de MON=4 en `run_genesis.ps1` no se requieren cambios; en una ejecución independiente:

```powershell
python genAudit.py --pst ../../assets/genus_pst.json --nnue ../../assets/genus_nnue.npy --bk ../../etc/bratko_kopec.epd --db C:/ruta/Bk.pb --out ../../data/audit_5000.json
```

Solo se reemplazan los módulos indicados en el ZIP. Aplicar sobre raíz `akkad`.
