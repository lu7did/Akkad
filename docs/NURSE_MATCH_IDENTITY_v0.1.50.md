# Nurse MATCH — Identidad UCI por brain (v0.1.50)

Parche incremental sobre el último MATCH v0.1.43. `--idA` y `--idB` son las identidades mostradas en la telemetría UCI, salida verbose, logs del proceso UCI y encabezados PGN. No se utiliza `a_player`/`b_player` para identificar motores UCI, porque esos campos contienen defaults de argparse.

No cambia comandos UCI, selección de jugadas, profundidad, pesos, tiempos ni la estructura de los datos CSV (`white_player`, `black_player`, etc.). Sin `--brain`, se preserva la etiqueta tradicional player|evaluator.

### Verificación

```powershell
python -m unittest discover -s nurse/tests -p 'test_match_identity_v0150.py' -v
```

Antes: `(sargon-plus|classic)` para ambos participantes. Después: `(dopey)` y `(pico)` según el turno.
