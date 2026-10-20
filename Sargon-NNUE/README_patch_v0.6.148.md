# Sargon-NNUE v0.6.148 — parche incremental `--level`

Corrige el cálculo de Elo de `sargon_brainmaker.py`: si `rating_elo` está ausente o es `null`, utiliza **400** para el cálculo. Un valor explícito inválido (cadena, booleano o no finito) sigue produciendo error.

Con `--save` se persiste el nuevo `rating_elo` y también se asigna 400 a los brains sin Elo que no hayan disputado partidas. Sin `--save` no se cambia `brains.json`. Todos los resultados se calculan contra los ratings de partida, sin depender del orden del Rally.

Ejemplo:

```powershell
python -m sargon_nnue.sargon_brainmaker --level --brain data/brains/brains.json --rally data/rally/rally.json --save
```

Aplicar sobre v0.6.147. Solo se cambian los módulos incluidos, sin modificar el Rally ni la lógica del motor. Para evitar contabilizar dos veces el mismo torneo, no ejecutar dos veces `--save` con el mismo Rally.
