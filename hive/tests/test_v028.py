"""Regression: UCI info frames are emitted only once using ℹ️."""
import contextlib
import importlib.util
import io
import pathlib
import queue
import sys
import time
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / "src" / "hive.py"
spec = importlib.util.spec_from_file_location("hive_telemetry_v028", PATH)
hive = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hive
spec.loader.exec_module(hive)

class NoDuplicateInfo(unittest.TestCase):
    def test_info_once(self):
        engine = object.__new__(hive.Transport)
        engine.name = "stockfish"
        engine.q = queue.Queue()
        engine.q.put("info depth 9 score cp 40 pv e2e4")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = engine.recv(time.monotonic() + 2)
        self.assertEqual(result, "info depth 9 score cp 40 pv e2e4")
        rows = stderr.getvalue().splitlines()
        self.assertEqual(len(rows), 1, rows)
        self.assertTrue(rows[0].startswith("ℹ️["), rows)
        self.assertNotIn("📮", rows[0])

    def test_regular_reply_preserves_marker(self):
        engine = object.__new__(hive.Transport)
        engine.name = "stockfish"
        engine.q = queue.Queue()
        engine.q.put("readyok")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(engine.recv(time.monotonic() + 2), "readyok")
        self.assertEqual(stderr.getvalue().count("📮["), 1)
        self.assertNotIn("ℹ️", stderr.getvalue())

if __name__ == "__main__":
    unittest.main()
