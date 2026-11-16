# Akkad / picoGenus — genSample.py v0.1.4

El universo de muestreo de `genSample.py` son exclusivamente las filas de
`positions` con evaluación Stockfish completa:

```sql
WHERE teacher_value IS NOT NULL AND teacher_at IS NOT NULL
```

Es el mismo criterio que `teacher.py --resume` utiliza para reconocer una
etiqueta completa. El valor `teacher_value=0` cuenta como valoración válida.
Un valor `teacher_cp` o `teacher_mate` parcial no equivale a una etiqueta
completa si faltan los campos requeridos.

El total de elegibles es el **100%** usado para `--pct`; también limita el valor
real de `--sample`, que tiene precedencia sobre `--pct` cuando aparecen ambos.
La telemetría presenta ese total y la cantidad seleccionada; la barra muestra
progreso respecto del número a copiar, en un único renglón de consola.

La selección permanece aleatoria y conserva todos los campos de las posiciones
seleccionadas y sus partidas relacionadas. La base de entrada se abre en modo
solo lectura y la salida se reemplaza como anteriormente.

```powershell
python .\genSample.py --in "C:\Data\sample_history.pb" --out "C:\Data\genus.pb" --pct 20
python .\genSample.py --in "C:\Data\sample_history.pb" --out "C:\Data\genus.pb" --sample 10000
```

Pruebas: `python -m pytest tests/test_gensample_labeled_v014.py -q`.
