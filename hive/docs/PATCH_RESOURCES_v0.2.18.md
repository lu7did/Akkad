# Hive v0.2.18 — bounded resource allocation

Base: Hive v0.2.16, patch `akkad_hive_picoSargon_stop_patch_v0.2.16.zip`.
Apply this incremental ZIP after v0.2.16 from the Akkad root. The picoSargon binaries and sources are unchanged by this patch.

## Configuration

Global intervals in minutes: `recalibration_min: 30`, `recalibration_max: 60`. Both must be finite and positive, with min <= max, except max=-1 disables mandatory recalibration and retains idle-only recalibration. For each engine defaults are `kmin: 0.0`, `kmax: 1.0`. Individual bounds are strictly `0 <= kmin < kmax <= 1`. Configured minima must sum to <= 1, maxima >= 1 (tolerance 1e-9). The same feasibility test applies to calibrated live resources. Startup fails before listeners are started if it cannot publish a valid initial allocation. A configuration with no statically configured engines is consequently rejected; discovery-only startup is not part of this revision.

The deployment's hive.yml was not included in the supplied v0.2.16 or November 24 baseline, so no full deployment YAML is overwritten. The new defaults apply even without editing it. To add them while preserving local configuration, run `python hive/tools/update_recalibration.py` from the root or pass the actual YAML path as the sole argument. The example file is a fragment, not a standalone configuration.

## Allocation

Every leaf motor is probed once when connected, with its configured one-move witness. Wall time is measured using perf_counter_ns (including communication). Allocation starts at kmin and distributes residual capacity proportional to inverse wall time, caps at kmax, redistributes the remainder, and validates bounds and total. A disconnect removes the cached measurement from the live set; reconnection or addition probes only that worker. Topology identity includes transport generation, not just count. No periodic recalibration is triggered by a normal search or stop. A global allocation is published under the registry lock, and a running search captures its weights when claiming resources. Integer quotas use largest remainders, deterministic ties by name, and keep the existing interleaving of candidate moves. Real-valued bounds cannot always hold exactly after integer rounding.

Existing concurrent-session support is retained: a session that can claim only a subset of connected engines calculates temporary bounded shares from the cached measurements, without probing or publishing a new global equilibrium. If this subset is infeasible, it waits for more resources, or uses the existing local-instance mechanism. Automatically spawned independent local workers use default bounds. If the connected set itself becomes infeasible, new searches cannot be assigned until valid resources return; the UCI layer reports the error rather than silently violating bounds. An existing in-flight search retains its assigned work. No failure-work redistribution is added here.

## Periodic recalibration

At min interval, opportunistically start when no engine is busy, reserved or connecting. If max=-1, no mandatory admission barrier is triggered. Otherwise, at max interval, close admission to new searches even while existing work is active; drain already assigned work before probing to prevent overlapping UCI transactions or losing their valid results. Thus max is a mandatory scheduling barrier, not an absolute guarantee that all probes finish exactly at 60 minutes. Existing search/transport timeouts still apply; a client whose waiting budget expires uses the existing cancellation fallback (a legal move, potentially unanalyzed). All live engines are probed sequentially. Global allocation publication is blocked until the batch completes. A failed periodic attempt is retried after retry_seconds, without treating failure as a successful full calibration. Incremental events do not reset the full-calibration timer. A new search arriving during the probe batch waits rather than preempting that batch. Telemetry: 🕛 for periodic events, ⚖️ for published allocation, ⛔ for integrity errors. Routine telemetry follows existing verbosity rules.

The existing remote-Hive parallel probe mechanism and network discovery protocol remain unchanged; hierarchical balancing is not redesigned here.

## Validation

Python syntax and 17 focused tests executed locally, including 500 randomly generated feasible bounded allocations, exact integer quotas, configuration checks, startup rejection, incremental loss/reconnect, idle and mandatory calibration, and prevention of partial allocation publication. The Python chess package is unavailable in the execution environment; tests use a minimal import stub when necessary and mocked probes/transports. No real engine integration, timing under actual load, network hierarchy or Windows deployment was exercised.
