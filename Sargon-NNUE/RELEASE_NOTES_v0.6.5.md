# Sargon-NNUE v0.6.5

## Baseline SARGON/CLASSIC aligned with Challenger

This release replaces the simplified v0.6.x baseline with a functional port of the
Sargon reference engine used by Challenger v0.1.0.

### CLASSIC evaluator
- material values 1.0/3.2/3.3/5.0/9.0 mapped to centipawns;
- piece activity;
- centre and extended-centre control;
- knight/bishop development;
- bishop pair;
- doubled and isolated pawns;
- king check, pawn shield and attacked king ring.

The evaluator remains independent of SARGON and exposes only the common
White-perspective centipawn contract.

### SARGON player
- alpha-beta minimax;
- quiescence search, default `qdepth=2` as in Challenger;
- forcing moves: captures, promotions and checks;
- Challenger move ordering;
- per-search transposition table;
- deadline checks;
- random tie-breaking with optional seed.

The player does not know which concrete evaluator is below it.

### CLI
- new `--qdepth`, default 2.

No additional search heuristics were introduced beyond the Challenger reference.
