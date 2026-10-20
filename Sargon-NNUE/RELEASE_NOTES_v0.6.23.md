# Sargon-NNUE v0.6.23

## TURBO candidate-entry guardrail

Corrección localizada sobre v0.6.22 motivada por un caso reproducible donde Adaptive Candidate Selection inició `depth=6` con `k=1`, consumió el presupuesto restante y terminó en guardrail con `root=0`, sin producir cálculo útil adicional.

### Cambio

Antes de iniciar Candidate Selection, TURBO estima el presupuesto mínimo seguro para completar al menos una raíz:

`required_one = (projected_full / N) * guard_error + (last_full / N)`

- `projected_full / N`: coste medio proyectado de una raíz del nuevo nivel.
- `guard_error`: peor error reciente `actual/proyectado` de niveles full-width completos o estimados por censura; nunca menor que 1.
- `last_full / N`: reserva dinámica equivalente al coste medio de una raíz del último nivel completo.

Si `remaining < required_one`, Candidate Selection no se inicia y se conserva inmediatamente el último nivel completo. No se introduce un umbral fijo en milisegundos ni una regla especial para `K=1`.

### Telemetría nueva

`⚡ TURBO candidates SKIP depth=... reason=insufficient-budget-for-one-root remaining_ms=... required_ms=... projected_root_ms=... guard=... reserve_ms=...`

### Sin cambios

- El estimador principal de `growth` continúa usando la mediana de las últimas observaciones.
- La fórmula normal de `K` no cambia una vez admitido Candidate Selection.
- BOOST no cambia.
- `--turbo 0` continúa siendo baseline estricto.
