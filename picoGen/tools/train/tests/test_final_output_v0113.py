"""Regression: completed genetic training must not fail while printing final result."""
import contextlib
import importlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@contextlib.contextmanager
def fake_connection(*_args):
    yield object()


class FinalOutputRegression(unittest.TestCase):
    def test_pst_completed_run_prints_output_and_writes_best(self):
        with patch.dict(sys.modules, {'chess': types.SimpleNamespace(Board=object, Move=object)}):
            module = importlib.import_module('genPST')
        with tempfile.TemporaryDirectory() as d:
            target = str(Path(d) / 'genus_pst.json')
            record = {'correct': 7, 'positions': 10, 'fitness': 49, 'parameters': {}}

            def fake_evolve(*args, **kwargs):
                kwargs['on_best'](record)
                kwargs['on_generation'](1, record)
                return record

            stdout = io.StringIO()
            with patch.object(sys, 'argv', ['genPST.py', '--in', 'dummy.pb', '--out', target]), \
                 patch.object(module, 'open_source', fake_connection), \
                 patch.object(module, 'load_labeled', return_value=[1]), \
                 patch.object(module, 'build_dataset', return_value=[1]), \
                 patch.object(module, 'evolve', side_effect=fake_evolve), \
                 contextlib.redirect_stdout(stdout):
                module.main()
            self.assertIn(f'PST output={target}', stdout.getvalue())
            self.assertTrue(Path(target).is_file())
            self.assertEqual(json.loads(Path(target).read_text())['fitness'], 49)
            self.assertTrue(Path(d, 'genus_pst.gen00001.json').is_file())

    def test_nnue_completed_run_prints_output_and_writes_best(self):
        module = importlib.import_module('genNNUE')
        with tempfile.TemporaryDirectory() as d:
            target = str(Path(d) / 'genus_nnue.npy')
            genes = np.array([1, -2, 3], dtype=np.int8)

            def fake_evolve(*args, **kwargs):
                kwargs['on_best'](genes, 25.0, 1)
                kwargs['on_generation'](1, genes, {'generation': 1, 'rmse_min_cp': 5.0})
                return genes, 25.0

            stdout = io.StringIO()
            with patch.object(sys, 'argv', ['genNNUE.py', '--in', 'dummy.pb', '--out', target]), \
                 patch.object(module, 'open_source', fake_connection), \
                 patch.object(module, 'load_labeled', return_value=[1]), \
                 patch.object(module, 'training_data', return_value=(None, None, np.array([20.]))), \
                 patch.object(module, 'evolve', side_effect=fake_evolve), \
                 contextlib.redirect_stdout(stdout):
                module.main()
            self.assertIn(f'NNUE output={target}', stdout.getvalue())
            np.testing.assert_array_equal(np.load(target), genes)
            self.assertTrue(Path(d, 'genus_nnue.gen00001.npy').is_file())

if __name__ == '__main__':
    unittest.main()
