# Sargon-NNUE v0.6.24

## TURBO Candidate Selection conservador

Corrige el caso observado en el que TURBO dimensionaba K para ocupar prácticamente todo el presupuesto y podía completar K-1 raíces antes de chocar con el guardrail, perdiendo todo el nivel selectivo.

La nueva política calcula primero la capacidad segura:

```text
safe_k = floor((remaining_ms - reserve_ms) / guarded_root_ms)
guarded_root_ms = (projected_full_ms / N) * guard_factor
reserve_ms = last_level_ms / N
```

y luego intenta sólo la mitad:

```text
k = floor(safe_k / 2)
```

Si la mitad es cero, no inicia Candidate Selection. No se modifican el estimador global de growth, Full Width ni BOOST.
