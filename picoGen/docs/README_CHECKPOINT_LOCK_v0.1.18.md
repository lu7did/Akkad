# picoGenus v0.1.18 — Windows checkpoint JSON lock recovery

## Observed failure

`PermissionError [WinError 5]` during `os.replace(temp, genus_nnue.best.json)`.
The temporary JSON was already closed by `Path.write_text`; an external lock,
read-only destination or filesystem permission can prevent a replace on Windows.
The log does not establish which of these caused the lock.

## Fix

- `json_atomic` writes through a context manager, flushes and fsyncs, then closes.
- Retry replacement up to six attempts (five short waits) on PermissionError.
- For **auxiliary** NNUE `.best.json` metadata only, if the destination remains
  locked, leave the complete temporary file in the same directory and report its
  exact path on stderr as WARNING, without failing the genetic training.
- Main checkpoint JSON files (PST) and NNUE `.npy` model files still fail on a
  persistent permission problem, rather than reporting a false successful save.
- No changes to fitness, evolution, model architecture, genesis paths, or CLI.

If a WARNING is shown, inspect whether the destination JSON is read-only, in
use by an editor or synced by an external process. Copy the preserved temporary
JSON to the destination after releasing the lock. The `.npy` checkpoint does not
need that JSON to load.

Tests simulate transient and persistent PermissionError; no native Windows
filesystem lock was available in this environment.
