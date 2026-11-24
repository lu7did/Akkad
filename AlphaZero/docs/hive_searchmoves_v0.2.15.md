# AlphaZero v0.2.15 — compatibility with Hive UCI

Base: `akkad(20261124-175149).zip`, with v0.2.65 changes already present.

## Fixed

- `go ... searchmoves <move1> [move2 ...]`: validate legal and unique UCI root moves and restrict the root *inside* MCTS (not by post-filtering `bestmove`). This applies to single-core and multicore root-parallel MCTS.
- Send scored `info depth 0 multipv N score cp X nodes ... time ... nps ... pv <root>` for each requested root and a single `bestmove` from that set. CP uses **root side-to-move** perspective. PV contains the root move (not a fabricated continuation).
- For a requested move without MCTS visits under a short budget, evaluate the child network directly and negate its Q to obtain a root-perspective score. The frame includes `string ALPHAZERO root_source=nnue-fallback`. The fallback requires neural inference and may exceed the nominal search deadline slightly.
- `go depth N` and `go qdepth N` are accepted for interoperation; **they have no operational meaning for MCTS**. `info depth 0` is intentionally honest, not an alpha-beta depth claim.
- Ordinary `go` without `searchmoves` retains unrestricted search and emits only the chosen root's scored PV.

## Example

```
uci
isready
position startpos
go depth 3 movetime 1500 searchmoves e2e4 d2d4 g1f3
```

Expect one scored `info ... pv <move>` per supplied move and `bestmove` among those roots.

## Build and smoke test

Rebuild AlphaZero with existing `AlphaZero/tools/{ps,bash,macOS}/build` scripts; this patch modifies the **common C++ frontend** used on Windows, Debian and macOS.

```
python AlphaZero/tests/uci_searchmoves_hive.py \
  --exe AlphaZero/X86/build/AlphaZero.exe \
  --weights AlphaZero/assets/t1-256x10-distilled-swa-2432500.pb.gz \
  --cores 4
```

The smoke test covers one and multiple restricted roots, plus a black-to-move position. A compiled binary with weights and LC0 backend is needed. Static and Python syntax checks alone do not establish runtime correctness.
