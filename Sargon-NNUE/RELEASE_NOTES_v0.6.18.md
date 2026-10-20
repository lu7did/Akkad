# Sargon-NNUE v0.6.18

## Telemetría de guardrails

- `GUARDRAIL` se emite siempre por la telemetría normal, independientemente de `--audit`.
- El formato `levels=nn/mm` indica la máxima profundidad completamente terminada (`nn`) sobre la profundidad objetivo (`mm`).
- `⚠️ GUARDRAIL` se usa cuando `nn > 0`: hubo una restricción, pero existe al menos una iteración completa confiable y se conserva la última.
- `❌ GUARDRAIL` se usa cuando `nn = 0`: no se terminó ni siquiera el primer nivel y sólo quedan opciones imperfectas/fallback.
- Para Sargón se conserva además `attempted`, `root`, nodos, tiempo y el tipo de fallback.
- Para Stockfish player, un corte por nodos usa el mismo criterio visual según la profundidad alcanzada; un timeout sin `bestmove` se reporta como `0/mm`.
