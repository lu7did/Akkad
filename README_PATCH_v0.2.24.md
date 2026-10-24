# picoAlpha v0.2.24 — Twin-core NN inference

Incremental patch over v0.2.23. `PA_DUAL_CORE_NN=ON` by default, revert with `-DPA_DUAL_CORE_NN=OFF`.

Core 0 retains UCI/MCTS and computes first half of output squares/actions/FC rows. Core 1 runs a persistent worker and computes disjoint second half. Per-layer generation handshake and `wfe/sev` synchronization. Never share scratch patches across cores.

Telemetry: `DUAL_CORE_INIT configured=1 active=1`, `NN_DUAL_CORE active=1 jobs=... wait_us=... core1_us=... timeouts=...`. `wait_us` counts wall time core 0 waits after finishing its slice, `core1_us` total compute time core 1, not an independent wall-clock latency.

Important: wait-time thresholds are diagnostic only. A stalled worker is still handled by existing watchdog; do not release job stack or workspace while worker is active. Existing watchdog-protection and MCTS guards remain.

Verification: native compilation available; hardware multicore/Pico SDK compilation not performed.
