# picoKeras v0.2.9 — shared model / iterative deepening

Supported: x86 Windows (TensorFlow C SavedModel), Debian and macOS (TFLite); not ARM.

## A. Share immutable model data

- **Windows:** Load SavedModel only once per model path + inference-thread budget and retain the resulting graph and **one session** through `std::shared_ptr`. Each `Evaluator` stores its own input/output bindings and allocation state, while **each TF_SessionRun invocation uses independent TF_Tensors and TF_Status**. Concurrent inference uses the TensorFlow C session's supported concurrent `TF_SessionRun` calls. The underlying session (including model variables) is shared: it is not valid to claim separate sessions. This assumes pure inference; no training or mutable assign ops should run. The shared session uses a total TF intra-op thread pool of `cores`, not one full pool per search worker.
- **macOS/Debian:** Share the read-only `tflite::FlatBufferModel` across workers; each worker retains its **own Interpreter** and allocated tensors. TFLite concurrency is therefore independent and thread-safe at the interpreter level. Each interpreter gets `infer_threads = max(1, cores/workers)`.
- Model lifetimes are managed by `shared_ptr` with a cache of `weak_ptr`; models are released once the final evaluator is destroyed.
- The single-session TensorFlow design differs from independent sessions. Cloning independently restored TensorFlow SavedModel sessions while sharing the same variables is not provided as a simple supported TensorFlow C primitive. If future models contain stateful training operations, concurrent sharing must be revisited.

## B. Iterative deepening

- With `--cores 1`, picoKeras runs the **unchanged** original depth-1 batched search.
- With `--cores N` (N>1) and `--depth D`, search completes depth 1, then depth 2, ..., up to D, with **one absolute deadline** across all iterations.
- Depth 1 evaluates children in a batch. At higher depths worker threads receive root branches from an atomic queue; negamax alpha-beta runs within each branch.
- Only fully completed iterations update the best move and score. Results of an interrupted iteration are discarded.
- Telemetry: `depth` = last **completed** depth, `requested_depth` = requested depth, `status=partial|complete`, `fallback=true|false`, and `level_ms` elapsed times per attempted level. Other counters (`nodes`, `evals`, `infer_ms`) accumulate across iterations and include partial work for performance analysis. `infer_ms` sums worker elapsed times and may be greater than wall time.
- If **no** level completes in time, the engine returns the first legal move only as an explicitly flagged emergency fallback (`depth=0`, `fallback=true`). It must not be interpreted as a neural best move.
- TensorFlow inference or TFLite `Invoke` is not interruptible mid-call; real wall time may overshoot the deadline if a call is already in progress.
- `bestmove` is still emitted synchronously at the end of `go` as before; the UCI command `stop` remains a no-op in this version, and real asynchronous stop would require a separate change.

## Test scope

`python picoKeras/tests/test_multicore_smoke.py`

`python picoKeras/tests/test_iterative_timeout.py`

The tests compile C++ against a **mock Evaluator**, checking both `MULTICORE=ON/OFF`, UCI output, depth completion and expiration. They do **not** test actual TensorFlow C/TFLite headers, linking, threading behavior or runtime performance. Those require builds on Windows, Debian and macOS.
