# AlphaZero v0.2.5 — persistent inference backends

## Symptom corrected
v0.2.4 instantiated one `LC0Inference` per MCTS worker **for each `go`** and discarded the instances when the search ended. A `ucinewgame` and any `setoption` also discarded the primary backend. Recreating LC0 backends may reload and/or reinitialize neural weights for every move.

## Behavior in v0.2.5
- One LC0 backend per worker, created lazily on the first `go` requiring it, retained across all future searches, `position`, and `ucinewgame` within the same UCI process.
- A change in `WeightsFile`, `Backend`, or `BackendOptions` invalidates all instances. Setting the same value does not invalidate them.
- Changing `BatchSize`, `Cores`, `TMax`, `Cpuct`, `Simulations`, `Timeout` or other search settings retains cached backends. Raising `Cores` creates only the missing instances; lowering `Cores` keeps unused instances warm.
- `MULTICORE` compile default stays ON in Windows, macOS and Debian build scripts; actual multicore selection requires CPU backend and `--cores N` (N>1).
- The LC0 backend objects must remain worker-exclusive: neural weights may be immutable, but inference backend buffers are not assumed thread safe.
- Individual MCTS search trees remain private and recreated per search; this patch does **not** cache tree positions between moves.
- A new UCI process (e.g. per TCP session or a process restart) still initializes its own backend pool. This patch does not implement interprocess memory sharing.
- Memory usage grows with worker count: depending on the backend, weights and intermediate buffers may be duplicated.

## Telemetry (stderr only)
`⚙️ AlphaZero backend_pool ready=4 cached=4 preparation_ms=0 weights=...`

Expect a larger `preparation_ms` on the first invocation; subsequent searches should generally be near zero. The network will still be *evaluated* during every simulation, but its weights are not loaded from disk again for every move.

## Checks
Run UCI `uci`, `isready`, `position startpos`, `go nodes 16 movetime 1000`, `ucinewgame`, `position startpos`, `go nodes 16 movetime 1000`, `quit`. Verify that the first search constructs the pool, that the second reports negligible preparation time, and that `stdout` carries only UCI while cache telemetry is on `stderr`. Rebuild binaries on all three target platforms; compilation against LC0 was not available in this development environment.
