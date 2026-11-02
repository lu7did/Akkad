python -m sargon_nnue.bellman_distiller `
  --misses "../data/bellman/bellman_misses.jsonl" `
  --db "../../../Chess_history_pb/pb/Bellman_pruned.pb" `
  --min-occurrences 2
