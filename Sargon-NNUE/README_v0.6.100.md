# Sargon-NNUE v0.6.100 — advertencia qdepth en Sargon histórico

Único archivo para reemplazar: `src/sargon_nnue/players/sargon_historical.py`.

Al crear el player `sargon`, si `qdepth` es distinto de cero emite una sola advertencia:

`❌ qdepth=2 inválido con player=sargon, ignored`

Continúa normalmente con `qdepth=0`. Si es cero, no emite advertencia. El resto de la implementación permanece intacto, incluido Sargon-Plus, RALLY, BOOST y TURBO.

Nota: actualmente el valor por defecto de `--qdepth` es 2. Como la fábrica no distingue entre valor explícito y valor por defecto, esa configuración también produce el aviso. No se cambió el parser ni el default, para restringir el parche a este player.
