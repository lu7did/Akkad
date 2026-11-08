# AlphaZero v0.2.9 — UCI telemetry and platform smoke tests

- Native engine mirrors incoming commands as `⬅️ UCI ...` and outgoing UCI frames as `➡️ UCI ...` to **stderr**.
- Wire UCI remains completely undecorated on **stdout** (required by the UCI standard).
- TCP Sargon listener mirrors every incoming and outgoing message to stderr. AlphaZero `info` is rendered as a compact `➡️ UCI info ...` plus two `📊 UCI info ...` detailed lines. The raw authoritative `info` frame still goes to the client unchanged.
- Native LC0 stdout/stderr messages and worker diagnostics remain on stderr.
- `test_smoke.sh` or `test_smoke.ps1` launches the native engine directly (no TCP server), checks `uciok`, `readyok`, a search and `bestmove`, and refuses decorated stdout.
- Build outputs remain under `AlphaZero/X86/build`, `AlphaZero/debian/build`, `AlphaZero/macOS/build`.
- MULTICORE compilation defaults to ON; no change to MCTS logic.

Note: `➡️ UCI` and `📊` are diagnostic renderings, **not** legal UCI command prefixes. Do not send these prefixes on TCP or native stdout.
