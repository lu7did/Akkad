# picoSargon v0.2.8 — experimental restored search

Based on v0.2.7 boot firmware and v0.2.5 Windows build script. Includes v0.2.2 lwIP/exception configuration. **Does not contain private generated_config.hpp.** Preserve yours.

Restored for C++: iterative deepening, alpha-beta, PVS, LMR, TT (256-entry bounded to Pico W SRAM), killer/history, capture order (MVV-LVA), bounded check extensions, reverse futility, quiescence. Transposition table conservatively disabled in history-sensitive positions.

Root depth defaults to **4 plies** on newly generated configuration; existing `include/generated_config.hpp` remains unchanged until regenerated with Python.

`python tools/generate_config.py --ssid YOUR_SSID --port 6110 --timeout-ms 15000 --plies 4`

**No auto-upgrade of configuration.** On board, print configured depth and memory per level, plus TT/cutoff totals. `heap_used/heap_free` come from newlib `mallinfo`; `stack_gap_approx` is an approximation of heap/stack distance, not exact SRAM remaining. `-1` means unavailable.

Build with `./build.ps1 -Board pico_w` on Windows after applying `src/engine.cpp`, `include/engine.hpp`, `src/pico_main.cpp` and regenerating config. With board changes none, previous board logic remains.

This is an **experimental reintroduction**, NOT bit-for-bit port of the older Doc implementation, and search tree will differ from v0.2.7. Confirm position legality, 2/4 ply and memory/stack margin on real Pico W before production. Previous 0.2.7 baseline preserved.
