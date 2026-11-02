# Bellman cache miss distillation

1. `sargon_match --telemetry` appends fallback and game_end records to `bellman_misses.jsonl` by default; override with `--bellman-misses-jsonl PATH`. Each fallback stores the original FEN, UCI action, NNUE cp/depth and color. The final game result is a separate `game_end` record linked by run_id/game.
2. `python -m sargon_nnue.bellman_distiller --misses data/bellman_misses.jsonl --db data/bellman.pb --min-occurrences 2`
3. `python -m sargon_nnue.bellman_export --in data/bellman.pb --json data/bellman.json`
4. Restart the player/listener to load new JSON.

Only completed, nontechnical game results are included. Outcomes are W/D/L from the action-playing side. Independent experiences are identified by (run_id,game,ply,side); importing the same JSONL twice is idempotent. At least two experiences of the exact same FEN-5 state and UCI move are required. The PGN-derived `bellman_actions` table is never changed. `bellman_distilled_experiences` retains every valid experience, and `bellman_distilled_actions` is a materialized aggregation of repeated observations. The exporter combines both while preserving the two source tables in SQLite.

**Caution:** WDL is the final match outcome, not proof of action quality. NNUE cp is stored for later analysis, not converted to a result. Different games might not be statistically independent if they share identical opening and deterministic opponents.
