import pathlib
import tempfile
import unittest
import numpy as np
from int8_pipeline import compare, tensor_audit, cpp_resolver_ops

class PipelineTests(unittest.TestCase):
    def test_compare(self):
        self.assertAlmostEqual(compare([1.0, 2.0], [1.1, 1.9]), 0.1)
        with self.assertRaises(ValueError):
            compare([1.0], [1.0, 2.0])
    def test_float_ops(self):
        details = [dict(index=0,name='x',dtype=np.int8),dict(index=1,name='z',dtype=np.float32)]
        ops = [dict(index=0,op_name='DEQUANTIZE',inputs=[0],outputs=[1])]
        a = tensor_audit(details, ops)
        self.assertEqual(len(a['float_tensors']),1)
        self.assertEqual(len(a['float_operations']),1)
    def test_registered(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'model.cpp'
            p.write_text('resolver.AddBatchMatMul(); resolver.AddFullyConnected(); resolver.AddRsqrt();')
            self.assertEqual(cpp_resolver_ops(p),{'BATCH_MATMUL','FULLY_CONNECTED','RSQRT'})
if __name__ == '__main__': unittest.main()
