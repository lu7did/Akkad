# v0.6.73 — Cerebrum 1.1 y RANDOM/NULL

Reemplazar `data/brains/brains.json` y `src/sargon_nnue/factory.py`.

* `alien` y `cerebrum` cambian exclusivamente su evaluador `cerebrum` (2.0) por `cerebrum-1.1`. La ruta a epoch-11-q.txt permanece sin cambios.
* `random|null` es aceptado por factory, tal como lo admiten brains y MATCH.
* No se modifica cerebrum.py (implementa v2.0), ni cerebrum_v11.py (implementa v1.1), ni los players.
* `cerebrum-1.1` exige cabecera name,author,parameters,wr,mt y 106722 parámetros para arquitectura 2x(768→128)→32→2.
* Sólo preflight real puede validar el archivo de pesos concreto (no fue adjuntado).
