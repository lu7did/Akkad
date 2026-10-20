# Sargon-NNUE v0.6.151 — orden descendente de Elo en `--list`

Parche incremental sobre **v0.6.150**.

- `--list` sin identificador: ordena por `rating_elo` **de mayor a menor**.
- Si dos perfiles tienen el mismo Elo, los ordena por `brainid` alfabéticamente.
- Sigue mostrando `ELO(nnn.nn)`; cuando falta `rating_elo` o es `null`, se usa 400.
- `--list ID` no cambia. No se modifican `--level`, `--elo` ni `--save`.

Ejecución: `python -m sargon_nnue.sargon_brainmaker --brain data/brains/brains.json --list`
