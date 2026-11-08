# AlphaZero v0.2.7 — formato compacto de telemetría

Aplica a AlphaZero C++ compartido: Windows X86, Debian Raspberry Pi y macOS. No modifica ARM.

- `stderr`: `⚙️ AlphaZero go mode=... timeout=... remaining=... increment=... movestogo=... sims=... batch=... cores=solicitados/activos`.
- `stderr`: `⚙️ AlphaZero backend new=n/reused/ready/cached preparation=... weights=...`.
- `stderr`: `⚙️ AlphaZero multicore setup=... msecs workers=...`.
- `stderr`: `🧠 AlphaZero core[i] stop=... sims=... alloc=... nodes=... nn_evals=... batches=... nn_ms=... msecs elapsed=...`; tiempos por núcleo con un decimal.
- Las métricas UCI en la consola del listener se presentan en **dos líneas** `📊 UCI info ...` abreviadas, impresas por el logger a `stderr`.
- El mensaje `info` nativo UCI enviado por `stdout` y reenviado por TCP **se mantiene sin alteraciones** para preservar compatibilidad UCI.
- `🧠 AlphaZero analysis` conserva sus métricas originales de distribución temporal.

No se cambian el motor MCTS, el batching, los parámetros de tiempo, MULTICORE ni los pesos.

Versiones: AlphaZero v0.2.7, Sargon-NNUE v0.6.200 (formato de log del listener).
