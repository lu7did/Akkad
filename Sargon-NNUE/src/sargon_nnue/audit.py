#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* audit.py
#* Implementa funciones del modulo audit
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()


class AuditLogger:
    """Thread-safe JSONL diagnostic logger.

    The logger is intentionally passive: audit mode must not alter move selection,
    evaluation, or UCI protocol behavior.  Every record contains a monotonic
    timestamp plus wall-clock time to make cross-session reconstruction easier.
    """

    def __init__(self, enabled: bool = False, path: str | None = None, *, eval_max: int = 5000):
        self.enabled = bool(enabled)
        self.path = str(Path(path or "sargon_audit.jsonl").expanduser().resolve())
        self.eval_max = max(0, int(eval_max))
        self._eval_written = 0
        self._eval_suppressed = 0
        if self.enabled:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self.event("audit_start", pid=os.getpid(), path=self.path, eval_max=self.eval_max)

    def event(self, event: str, **fields: Any) -> None:
        if not self.enabled:
            return
        record = {
            "event": event,
            "time_unix": time.time(),
            "time_monotonic": time.monotonic(),
            **fields,
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str)
        with _LOCK:
            with open(self.path, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(line + "\n")

    def evaluator_event(self, **fields: Any) -> None:
        """Write evaluator calls up to eval_max, then count suppressed calls."""
        if not self.enabled:
            return
        if self._eval_written < self.eval_max:
            self._eval_written += 1
            self.event("stockfish_evaluator", eval_index=self._eval_written, **fields)
        else:
            self._eval_suppressed += 1

    def summary(self) -> None:
        if self.enabled and self._eval_suppressed:
            self.event(
                "audit_summary",
                evaluator_records_written=self._eval_written,
                evaluator_records_suppressed=self._eval_suppressed,
            )
