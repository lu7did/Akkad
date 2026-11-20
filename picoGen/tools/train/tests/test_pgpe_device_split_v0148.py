"""Regression checks for OOM fix v0.1.48; no XPU or EvoTorch required."""
import ast
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'genPGPE.py'

class DeviceSplitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.text)

    def test_device_split_and_host_dataset(self):
        self.assertIn("search_device = torch.device('cpu') if device.type == 'xpu' else device", self.text)
        for var in ('train_x','train_n','train_y'):
            self.assertIn(f'{var} = torch.as_tensor(', self.text)
        self.assertGreaterEqual(self.text.count("device='cpu'"), 4)
        self.assertIn('device=str(search_device)', self.text)
        self.assertIn('device=search_device', self.text)

    def test_fitness_runs_on_selected_gpu_not_cpu_optimizer(self):
        self.assertIn('population_fitness(solutions.to(device)', self.text)
        self.assertIn('individuals_chunk=args.population_chunk).to(search_device)', self.text)
        self.assertIn('current_batch[0] = gpu_batch(idx)', self.text)
        self.assertIn('population_fitness(candidates.to(device)', self.text)

    def test_resume_state_mapped_to_optimizer_device(self):
        self.assertIn('map_location=search_device', self.text)
        self.assertIn('restore_pgpe(searcher, ck, search_device)', self.text)
        self.assertIn("CHECKPOINT_FORMAT = 'picogen-pgpe-768x16-prob-v1'", self.text)

    def test_original_architecture_fitness_unmodified(self):
        self.assertIn("'picogen-pgpe-768x16-prob-v1'", self.text)
        self.assertIn('activation=clamp(0,1) objective=probability-MSE', self.text)
        self.assertIn('from gen_pgpe_core import (PARAMS, HIDDEN, MANIFEST, load_filtered_csv,', self.text)

if __name__ == '__main__':
    unittest.main()
