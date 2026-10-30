import ast
import pathlib
import unittest

HERE = pathlib.Path(__file__).parent

class TestPatch(unittest.TestCase):
    def test_files_compile(self):
        for name in ('export_graph.py', 'int8_pipeline.py'):
            ast.parse((HERE/name).read_text(encoding='utf8'))
    def test_export_preserves_dynamic_normalization(self):
        source = (HERE/'export_graph.py').read_text(encoding='utf8')
        for term in ('ops.mean(inputs', 'ops.multiply(centered, centered)', 'self.epsilon', 'self.gamma', 'self.beta', 'export_model.set_weights'):
            self.assertIn(term, source)
        self.assertNotIn('FrozenNorm', source)
    def test_pipeline_is_opt_in_and_verifies(self):
        source = (HERE/'int8_pipeline.py').read_text(encoding='utf8')
        self.assertIn("action='store_true'", source)
        self.assertIn('fully_int8_by_tensor_check', source)
        self.assertIn('original_keras_vs_fp32', source)
        self.assertIn('preserve_rejected(', source)

if __name__ == '__main__': unittest.main()
