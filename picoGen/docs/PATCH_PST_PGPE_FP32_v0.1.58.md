# Akkad / picoGen / Nurse: PST con EvoTorch PGPE v0.1.58

## Objetivo y compatibilidad

- MON 6 usa **PGPE (EvoTorch)** para el PST, en vez del algoritmo genético previo de mutación gaussiana 3 %. MON 7 Grumpy NNUE **no cambia**.
- Se conserva `gen_sargon_core.py` y su función `evaluate`, incluidos factores posicionales, recorte ±2000 cp y override táctico de mate en una. La matriz de características es una vectorización del mismo evaluador, no una heurística sustituta.
- Material inicial de Grumpy: peón 100, caballo 300, alfil 300, torre 500, dama 900 cp. **Todos evolucionan libremente**, dentro de límites compatibles con los coeficientes PST existentes (peón 1..2047).
- `CALIBRATION_SCALE` queda **fijo en 100** para eliminar redundancia entre escala global y material.
- El criterio único es MSE en centipeones comparado con las etiquetas de Stockfish; se excluye exactamente `cp=0`. El mejor modelo se selecciona por RMSE sobre T77 sin utilizarla para modificar parámetros. Importante: se informa tanto la mejora en T79 como T77.
- PGPE optimiza coordenadas normalizadas con amplitudes diferentes para material y factores posicionales. No usa gradientes ni Adam de NNUE.
- `best.json` continúa usando `format=picogen-binpack-genetic-fp32-v1`, `model=PST`, diccionario `parameters`, y `genes_fp32`, de modo que el contrato del evaluador `genus-pst` se preserva. Nurse permite peones FP32 positivos no necesariamente iguales a 100 solo para el formato FP32. Los formatos antiguos conservan la restricción de 100.
- `best.pst-pgpe-v1.latest.pt` contiene el checkpoint de PGPE con distribución, optimizador, población, RNG, mejor modelo y generación. No mezclar con los checkpoints del PST anterior.

## Ejecutar SOLO PST sin interrumpir la NNUE

Desde `akkad/picoGen/tools/train`:

```powershell
.\run_genesis_binpack.ps1 --mon 6 --pst-only --generations 100
```

MON 6 reutiliza `train.csv`/`validation.csv` del run `binpack-pgpe-nonzero-001`, toma hasta 800.000 posiciones elegibles de T79 y hasta ~147.000 de T77, usa 50 participantes y 40.000 posiciones T79 por generación. No recalcula la NNUE ni MON 8, ni modifica `MON.state`. Archiva **solo** los modelos PST existentes antes de reiniciar.

**El auditor MON 8 no se ejecuta con `--pst-only`**. Para una comparación independiente completa posterior, ejecutar MON 8 con la nueva PST y la NNUE existente. El archivo `audit.json` anterior queda desactualizado respecto a PST tras la corrida.

## Pruebas

```powershell
python -m unittest discover -s .\tests -p test_pst_pgpe_v0158.py
```

Se verifica numéricamente la equivalencia de la extracción de características con el evaluador histórico en posiciones de referencia y la libertad del valor del peón. Requiere `numpy`, `python-chess`, `torch` y `evotorch` para el entrenador.

## Restricciones

No extrapolar el rendimiento ajedrecístico de la minimización del MSE de Stockfish. El PST sigue siendo una heurística fija con 28 coeficientes: no introduce nueva representación ni red neuronal. Una pérdida baja en los datos T77 no garantiza fuerza en partidas.
