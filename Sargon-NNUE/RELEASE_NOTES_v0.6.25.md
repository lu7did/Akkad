# Sargon-NNUE v0.6.25

## TURBO return telemetry

- Adds explicit `⚡ TURBO RETURN last-complete ...` telemetry when a deeper TURBO level is abandoned and the engine returns the move from the last fully completed level.
- Reports `depth`, `attempted`, `reason`, `bestmove`, and `score_cp`.
- Reasons include `insufficient-budget-for-one-root`, `conservative-half-is-zero`, `candidate-incomplete`, and `candidate-disabled-or-unavailable`.
- Search logic, BOOST, TURBO sizing, growth estimation, and fallback behavior are unchanged from v0.6.24.
