# Sargon-NNUE v0.6.84 — corrección de integración rating_elo

Reemplazar solamente `src/sargon_nnue/sargon_match.py`.

Causa comprobada: MATCH convertía todos los campos recibidos de `brains.get()` en parámetros `--a-...` y `--b-...`, incluidos los metadatos ELO. Ahora transmite únicamente las claves `ENGINE_KEYS` autorizadas en `brains.py`.

`rating_elo` permanece en `brains.json`, sin enviarse a MATCH ni al listener. Se conserva el resto del comportamiento de MATCH v0.6.76 (telemetría sin parpadeos y sin Winner).

Verificación rápida desde `scripts`:
`python -m sargon_nnue.sargon_match --brain ../data/brains/brains.json --idA classic --idB messy --pairs 1 --max-plies 4 --csv ../data/runs/prueba084.csv`

Esta prueba realiza partidas cortas: hacerlo cuando no haya otro RALLY activo y elegir una ruta de salida distinta de las reales.
