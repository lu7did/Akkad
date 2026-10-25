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
#* test_lc0_windows_dll_v06122.py
#* Isolated regression test for Windows DLL lookup (no LC0/chess required).
#* v0.6.153
#=================================================================================================================*
"""Isolated regression test for Windows DLL lookup (no LC0/chess required)."""
import builtins
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'sargon_nnue' / 'evaluators' / 'lc0.py'


class WindowsDLLTests(unittest.TestCase):
    def setUp(self):
        self.saved = {}
        for key in ('chess', 'sargon_nnue', 'sargon_nnue.evaluators',
                    'sargon_nnue.evaluators.base', 'sargon_nnue.evaluators.lc0',
                    'lczero', 'lczero.backends'):
            self.saved[key] = sys.modules.get(key)
        chess = types.ModuleType('chess')
        chess.Move = type('Move', (), {})
        chess.Board = type('Board', (), {})
        chess.WHITE = True
        sys.modules['chess'] = chess
        for name in ('sargon_nnue', 'sargon_nnue.evaluators', 'lczero'):
            package = types.ModuleType(name)
            package.__path__ = []
            sys.modules[name] = package
        base = types.ModuleType('sargon_nnue.evaluators.base')
        base.Evaluator = object
        base.EvaluatorError = RuntimeError
        sys.modules[base.__name__] = base
        backend = types.ModuleType('lczero.backends')
        backend.Weights = lambda filename: filename
        backend.Backend = lambda **kwargs: object()
        backend.GameState = type('GameState', (), {})
        sys.modules[backend.__name__] = backend
        spec = importlib.util.spec_from_file_location('sargon_nnue.evaluators.lc0', SOURCE)
        self.lc0 = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.lc0
        spec.loader.exec_module(self.lc0)

    def tearDown(self):
        for name, module in self.saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def test_windows_registers_dll_directory_before_import_and_keeps_handle(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / 'venv'
            dlls = prefix / 'Lib' / 'site-packages' / '.lczero_bindings.mesonpy.libs'
            dlls.mkdir(parents=True)
            weights = Path(tmp) / 'weights.pb.gz'
            weights.write_bytes(b'fake-network')
            handle = object()
            records = []
            fake_os = types.SimpleNamespace(name='nt', add_dll_directory=lambda p: (records.append(('add', p)), handle)[1])
            real_import = builtins.__import__

            def traced_import(name, *args, **kwargs):
                if name == 'lczero.backends':
                    records.append(('import', name))
                return real_import(name, *args, **kwargs)

            with mock.patch.object(self.lc0, 'os', fake_os), \
                 mock.patch.object(self.lc0, 'sys', types.SimpleNamespace(prefix=str(prefix))), \
                 mock.patch('builtins.__import__', side_effect=traced_import):
                evaluator = self.lc0.LC0Evaluator(str(weights))
            self.assertEqual(records, [('add', str(dlls)), ('import', 'lczero.backends')])
            self.assertIs(evaluator._lc0_dll_handle, handle)

    def test_non_windows_never_registers_dll_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            weights = Path(tmp) / 'weights.pb.gz'
            weights.write_bytes(b'fake-network')
            fake_os = types.SimpleNamespace(name='posix', add_dll_directory=lambda p: self.fail('should not be called'))
            with mock.patch.object(self.lc0, 'os', fake_os):
                evaluator = self.lc0.LC0Evaluator(str(weights))
            self.assertIsNone(evaluator._lc0_dll_handle)

    def test_windows_without_mesonpy_dll_dir_does_not_fabricate_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            weights = Path(tmp) / 'weights.pb.gz'
            weights.write_bytes(b'fake-network')
            fake_os = types.SimpleNamespace(name='nt', add_dll_directory=lambda p: self.fail('missing dir'))
            with mock.patch.object(self.lc0, 'os', fake_os), \
                 mock.patch.object(self.lc0, 'sys', types.SimpleNamespace(prefix=tmp)):
                evaluator = self.lc0.LC0Evaluator(str(weights))
            self.assertIsNone(evaluator._lc0_dll_handle)


if __name__ == '__main__':
    unittest.main()
