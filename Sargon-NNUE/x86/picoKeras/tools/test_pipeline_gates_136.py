import ast
from pathlib import Path
import unittest

class PipelineGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=Path(__file__).with_name('int8_pipeline.py').read_text(encoding='utf-8')
        cls.tree=ast.parse(cls.src)
    def test_numerics_precede_runtime_gate(self):
        self.assertLess(self.src.index("report['steps']['fp32_vs_int8']"), self.src.index("if runtime_missing:\n            # Save"))
    def test_no_published_int8_when_runtime_missing(self):
        missing=self.src[self.src.index('if runtime_missing:\n            # Save'):self.src.index("else:\n            if a.mode == 'convert':",self.src.index('if runtime_missing:\n            # Save'))]
        self.assertNotIn("report['published_int8']",missing)
        self.assertIn('runtime_unverified.tflite',missing)
    def test_valid_python(self):
        self.assertIsInstance(self.tree,ast.Module)

if __name__=='__main__': unittest.main()
