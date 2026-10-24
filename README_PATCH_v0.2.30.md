# picoAlpha v0.2.30 — Bounded Board + MCTS + Network

**Apply on v0.2.29.** Only files changed by this patch are included.

* Dual core still forcibly OFF (v0.2.28 setting).
* Static MCTS arena unchanged at 6144 nodes.
* Board uses bounded inline history (256 position keys) and undo stack (256). Move-generation `legal()` and `pseudo()` use fixed 256-move buffers. Existing `std::vector` entry points remain as compatibility wrappers for non-search clients; MCTS and UCI error recovery use the fixed API.
* Compact search history uses a fixed 256-element array; input history is copied into static per-search scratch, not an allocating vector.
* MCTS legal moves, policy indices and softmax scratch use reusable fixed arrays (not recursive stack arrays). Board search object is constructed before the first go.
* Neural workspace's vectors are replaced by bounded inline arrays with sizes appropriate to their layer; all `resize` and `assign` operations are bounded writes, not allocations. Policy `Result` refers to the reused workspace (no heap copy). This reference remains valid until the next inference; MCTS consumes it immediately.
* Neural convolution patch scratch uses static 1024-element arrays in **single-core mode** only. Do not enable dual-core with the present shared kernel scratch design.
* The existing UCI strings/TCP, Pico SDK, lwIP, exception machinery and startup FEN parsing are **not** claimed to be allocation free.
* New `MEM_ENGINE_FIXED` log records fixed capacities and overall observed heap delta. It is *not* a per-subsystem allocation counter.

## Capacity limits

Board history and undo stack: 256; CompactHistory: 256; maximum number of moves generated at once: 256. Overflow throws a bounded exception instead of writing beyond memory. Very long (>255 halfmoves, inclusive of search depth) games will produce recoverable errors rather than silent overflow; a further rolling-history design would be needed for those.

## Tests

Native compilation C++17 (`board.cpp`, `mcts.cpp`, `net.cpp`) with PA_SEGMENTED_TREE=1, PA_COMPACT_HISTORY=1, PA_DUAL_CORE_NN=0, PA_NN_FC_INT8=1. `tests/heap_audit_native.cpp` overrides `operator new` to count allocations after startup: three sequential four-simulation searches and 100 legal board moves all recorded **0 additional operator new calls**. It is a targeted native smoke test, not an exhaustive static proof or ARM physical test. First-shot native run and repeated tests passed. C++17 syntax also passed with PA_NN_WORKSPACE=0 (static workspace fallback).

**ARM cross-build and full-length physical game not executed here.** Firmware uses static arrays; inspect linker SRAM usage before flashing. No further MCTS node restriction added.
