# Sargon-NNUE v0.6.19

## Guardrail telemetry generalized

- `⚠️ GUARDRAIL` / `❌ GUARDRAIL` is normal telemetry, never audit-only.
- SARGON+ now emits the same `levels=nn/mm` guardrail message as SARGON when a time restriction interrupts iterative deepening.
- `⚠️` means at least one complete level exists and the move is chosen from the last complete level.
- `❌` means no complete level exists; only imperfect/fallback information is available.
- SARGON with Cerebrum, Cerebrum-v1.1 or Stockfish evaluator uses iterative deepening so expensive evaluators can safely fall back to the last complete level.
- Canonical SARGON with the classic evaluator preserves its historical direct-search behavior; if that direct search times out it reports `levels=0/N`, because no complete lower-level iteration was actually computed.
- SARGON+ passes telemetry/audit hooks through its constructor, so guardrails are visible in normal execution regardless of evaluator (classic, Cerebrum, Stockfish, etc.).
- Startup `⚙️ EXEC` telemetry now states the effective iterative-deepening mode, guardrail policy, and SARGON+ boost.

## Scope of node guardrails

- The SARGON/SARGON+ search currently has no configurable node ceiling, so its native guardrail is time/depth completion.
- Stockfish player retains its node guardrail and reports it with the same severity convention.
- No synthetic node limit was added to SARGON/SARGON+; this release only reports limits that actually exist.
