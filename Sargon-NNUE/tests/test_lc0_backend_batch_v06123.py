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
#* test_lc0_backend_batch_v06123.py
#* Regression: LC0 bindings evaluate(inputs) requires Sequence[Input].
#* v0.6.153
#=================================================================================================================*
"""Regression: LC0 bindings evaluate(inputs) requires Sequence[Input].

Run with standard library only: no lczero-bindings or python-chess required.
"""
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'sargon_nnue' / 'evaluators' / 'lc0.py'


class FakeOutput:
    def p_softmax(self, *indices):
        assert indices == (7,)
        return [1.0]

    def q(self):
        return 0.4

    def d(self):
        return 0.2


class FakeBackend:
    instances = []

    def __init__(self, **kwargs):
        self.seen_inputs = None
        self.__class__.instances.append(self)

    def evaluate(self, inputs):
        if not isinstance(inputs, list) or len(inputs) != 1 or inputs[0] != 'fake-input':
            raise TypeError('evaluate(): expected a sequence of one Input')
        self.seen_inputs = inputs
        return [FakeOutput()]


class FakeGameState:
    def __init__(self, fen=None, moves=None):
        self.fen = fen

    def as_input(self, backend):
        return 'fake-input'


class FakeBoard:
    move_stack = []
    legal_moves = ()
    turn = True

    def is_game_over(self, claim_draw=False):
        return False

    def copy(self, stack=False):
        return self

    def fen(self):
        return 'fake-fen'


class TestBatchAPI(unittest.TestCase):
    def test_single_input_is_submitted_as_list_and_wdl_recovered(self):
        saved = {}
        names = ('chess', 'sargon_nnue', 'sargon_nnue.evaluators',
                 'sargon_nnue.evaluators.base', 'sargon_nnue.evaluators.lc0',
                 'lczero', 'lczero.backends')
        for name in names:
            saved[name] = sys.modules.get(name)
        try:
            chess = types.ModuleType('chess')
            chess.Move = type('Move', (), {})
            chess.Board = FakeBoard
            chess.WHITE = True
            sys.modules['chess'] = chess
            for name in ('sargon_nnue', 'sargon_nnue.evaluators', 'lczero'):
                pkg = types.ModuleType(name)
                pkg.__path__ = []
                sys.modules[name] = pkg
            base = types.ModuleType('sargon_nnue.evaluators.base')
            base.Evaluator = object
            base.EvaluatorError = RuntimeError
            sys.modules[base.__name__] = base
            backends = types.ModuleType('lczero.backends')
            backends.Weights = lambda path: path
            backends.Backend = FakeBackend
            backends.GameState = FakeGameState
            sys.modules[backends.__name__] = backends
            spec = importlib.util.spec_from_file_location('sargon_nnue.evaluators.lc0', SOURCE)
            lc0 = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = lc0
            spec.loader.exec_module(lc0)
            with tempfile.TemporaryDirectory() as tmp:
                network = Path(tmp) / 'network.pb.gz'
                network.write_bytes(b'weights')
                with mock.patch.object(lc0, 'os', types.SimpleNamespace(name='posix')):
                    evaluator = lc0.LC0Evaluator(str(network), backend='eigen')
                move = object()
                with mock.patch.object(lc0, '_normalize_moves', return_value=([move], [7])):
                    result = evaluator.evaluate_pv(FakeBoard())
                self.assertEqual(evaluator._backend.seen_inputs, ['fake-input'])
                self.assertEqual(result.policy[move], 1.0)
                self.assertAlmostEqual(result.w, 0.6)
                self.assertAlmostEqual(result.d, 0.2)
                self.assertAlmostEqual(result.l, 0.2)
        finally:
            for name, original in saved.items():
                if original is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = original


if __name__ == '__main__':
    unittest.main()
