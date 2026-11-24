"""Regression tests for legacy Nurse UCI adapter perspective boundaries.

Run: python -m unittest discover -s nurse/tests -p test_uci_stm_legacy_boundaries_v0266.py -v
No chess binary/model/network required.
"""
import ast
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
UTIL = ROOT / "nurse/src/nurse/_legacy/score_perspective.py"


def source(relpath):
    return (ROOT / relpath).read_text(encoding="utf-8")


class PerspectiveContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("legacy_perspective", UTIL)
        cls.util = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.util)

    def test_sign_both_colors(self):
        for score in (-123, 0, 456):
            with self.subTest(score=score):
                self.assertEqual(score, self.util.stm_to_white(score, True))
                self.assertEqual(-score, self.util.stm_to_white(score, False))
                self.assertEqual(score, self.util.white_to_stm(score, True))
                self.assertEqual(-score, self.util.white_to_stm(score, False))
                self.assertEqual(score, self.util.white_to_stm(self.util.stm_to_white(score, False), False))

    def test_uci_adapters_convert_to_legacy_white_choice(self):
        for player in ("picosargon_uci", "picoalpha_uci", "tinyalpha_uci", "picokeras_uci"):
            path = f"nurse/src/nurse/_legacy/players/{player}.py"
            program = ast.parse(source(path))
            calls = [node for node in ast.walk(program)
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                     and node.func.id == "MoveChoice"]
            self.assertTrue(calls, player)
            self.assertTrue(any(any(isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "stm_to_white"
                    for arg in call.args for child in ast.walk(arg)) for call in calls), player)

    def test_keras_returns_white_score(self):
        path = "nurse/src/nurse/_legacy/players/keras_player.py"
        s = source(path)
        self.assertIn("score = int(vals[index])  # MoveChoice contract: WHITE-relative", s)
        self.assertNotIn("score = int(vals[index]) if side == chess.WHITE else -int(vals[index])",s)

    def test_generic_uci_runtime_black_and_white(self):
        import queue
        import time
        from types import SimpleNamespace
        from dataclasses import dataclass
        from unittest.mock import Mock

        @dataclass
        class FakeChoice:
            move: object
            score_cp: int
            depth: int
            nodes: int
            elapsed_ms: float
            source: str

        class FakeMove:
            def __init__(self, token): self.token = token
            def __str__(self): return self.token

        fake_chess = SimpleNamespace(Board=object, Move=SimpleNamespace(from_uci=FakeMove))
        parsed = ast.parse(source("nurse/src/nurse/_legacy/players/uci_external.py"))
        cls = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == "ExternalUCIPlayer")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "choose")
        program = ast.Module(body=[method], type_ignores=[])
        ast.fix_missing_locations(program)
        scope = dict(chess=fake_chess, time=time, queue=queue, MoveChoice=FakeChoice,
                     PlayerError=RuntimeError, stm_to_white=self.util.stm_to_white,
                     MATE_CP=100000)
        import re
        scope.update(re=re, _INFO_DEPTH_RE=re.compile(r"\bdepth\s+(\d+)\b"),
                     _INFO_NODES_RE=re.compile(r"\bnodes\s+(\d+)\b"),
                     _INFO_SCORE_RE=re.compile(r"\bscore\s+(cp|mate)\s+(-?\d+)\b"))
        exec(compile(program, "uci_external.choose", "exec"), scope)
        for turn, expected in ((True, 123), (False, -123)):
            with self.subTest(turn_white=turn):
                q = queue.Queue()
                q.put("info depth 5 nodes 142 score cp 123 time 100")
                q.put("bestmove e2e4")
                fake_engine = SimpleNamespace(_send=Mock(), movetime_ms=1000,
                                              timeout_ms=5000, name="fake-uci", q=q)
                fake_board = SimpleNamespace(fen=lambda: "fake fen", turn=turn,
                                             legal_moves=[FakeMove("e2e4")])
                # Value-based move equality, as python-chess does for Move objects.
                FakeMove.__eq__ = lambda x, y: isinstance(y, FakeMove) and x.token == y.token
                result = scope["choose"](fake_engine, fake_board)
                self.assertEqual(result.score_cp, expected)
                self.assertEqual((result.depth, result.nodes), (5, 142))

    def test_keras_white_score_runtime(self):
        import time
        from types import SimpleNamespace
        from dataclasses import dataclass
        @dataclass
        class FakeChoice:
            move: object
            score_cp: int
            depth: int
            nodes: int
            elapsed_ms: float
            source: str
        fake_chess = SimpleNamespace(Board=object, WHITE=True)
        parsed = ast.parse(source("nurse/src/nurse/_legacy/players/keras_player.py"))
        cls = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == "KerasPlayer")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "choose")
        program = ast.Module(body=[method], type_ignores=[])
        ast.fix_missing_locations(program)
        scope = dict(chess=fake_chess, time=time, MoveChoice=FakeChoice, PlayerError=RuntimeError)
        exec(compile(program, "keras_player.choose", "exec"), scope)
        class Move:
            def __init__(self, token): self.token=token
            def uci(self): return self.token
        for turn, expected_score, chosen in ((True, 80, "e2e4"), (False, -60, "d2d4")):
            moves=[Move("e2e4"),Move("d2d4")]
            fake_board=SimpleNamespace(turn=turn,legal_moves=moves)
            def evaluate_children(board, moves, depth, stats): return [80,-60]
            engine=SimpleNamespace(plies=1,_evaluate_children=evaluate_children,telemetry=None)
            result=scope["choose"](engine,fake_board)
            self.assertEqual(result.move.uci(), chosen)
            self.assertEqual(result.score_cp, expected_score)

    def test_legacy_uci_converts_white_at_output(self):
        s = source("nurse/src/nurse/_legacy/uci.py")
        self.assertIn("choice.score_cp if board.turn == chess.WHITE else -choice.score_cp", s)

    def test_worker_converts_white_at_output(self):
        s = source("nurse/src/nurse/worker.py")
        self.assertIn('score_cp=int(getattr(result,"score_cp",0)) * (1 if board.turn==chess.WHITE else -1)', s)

    def test_training_stays_white(self):
        s = source("picoGen/tools/train/gen_csv_dataset.py")
        self.assertIn("score_white_cp", s)
        s = source("nurse/src/nurse/evaluator_client.py")
        self.assertIn("perspective", s)
        self.assertIn("white", s)

if __name__ == "__main__":
    unittest.main()
