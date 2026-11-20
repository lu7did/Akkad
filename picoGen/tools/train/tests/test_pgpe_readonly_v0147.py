"""v0.1.47 regression: EvoTorch vectorized objective receives ReadOnlyTensor."""
import sys
import unittest
from pathlib import Path
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gen_pgpe_core import PARAMS, population_fitness

class ReadOnlyLikeTensor(torch.Tensor):
    # Matches the specific protection that caused the XPU traceback.
    def __iadd__(self, other):
        raise TypeError('The contents of a ReadOnlyTensor cannot be modified')

class PGPEReadOnlyRegression(unittest.TestCase):
    def test_readonly_evolution_population(self):
        rng = np.random.default_rng(51)
        g = torch.tensor(rng.normal(0, 0.2, (3, PARAMS)).astype('float32'))
        ro = g.as_subclass(ReadOnlyLikeTensor)
        x = torch.tensor(rng.integers(0, 768, (11,32)), dtype=torch.long)
        c = torch.tensor([2,5,7,12,16,20,25,32,11,6,4], dtype=torch.long)
        y = torch.linspace(-400, 400, 11)
        want = population_fitness(g, x, c, y, examples_chunk=4, individuals_chunk=2)
        got = population_fitness(ro, x, c, y, examples_chunk=4, individuals_chunk=2)
        self.assertEqual(type(got), torch.Tensor)
        torch.testing.assert_close(got, want)
        torch.testing.assert_close(ro.as_subclass(torch.Tensor), g)

    def test_single_chunk_readonly(self):
        g = torch.zeros((1, PARAMS)).as_subclass(ReadOnlyLikeTensor)
        x = torch.zeros((1,32), dtype=torch.long)
        c = torch.ones(1, dtype=torch.long)
        y = torch.zeros(1)
        result = population_fitness(g,x,c,y)
        self.assertEqual(result.item(),0.0)

if __name__ == '__main__': unittest.main()
