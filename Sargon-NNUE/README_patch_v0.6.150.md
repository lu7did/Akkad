# Sargon-NNUE v0.6.150 — `brainmaker --list`

Parche incremental sobre v0.6.149. Modifica únicamente `src/sargon_nnue/sargon_brainmaker.py` y la versión del paquete.

- `--list` sin ID: orden ascendente de `rating_elo`; desempate alfabético por brainid.
- Incluye `ELO(nnn.nn)` explícito por cada brain en el resumen.
- `rating_elo` ausente o `null`: se muestra **400.00**, sin alterar `brains.json`.
- `rating_elo` explícito inválido: error de validación; no se reinterpreta como 400.
- `--list ID`: conserva la consulta de un perfil individual e incluye su Elo.
- No altera los cálculos de `--level`, `--elo` ni las reglas de `--save`.

Ejemplo: `python -m sargon_nnue.sargon_brainmaker --list --brain data/brains/brains.json`
