import tempfile
from pathlib import Path
import unittest
from int8_pipeline import preserve_rejected

class RejectedModelTests(unittest.TestCase):
    def test_persist_rejected_separately(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            fp=base/'ref.tflite'
            it=base/'model.int8.tflite'
            r={}
            preserve_rejected(fp,b'FP32',it,b'TFL3DATA',r)
            self.assertEqual(fp.read_bytes(),b'FP32')
            self.assertEqual((base/'model.int8.tflite.rejected.tflite').read_bytes(),b'TFL3DATA')
            self.assertFalse(it.exists())
            self.assertEqual(r['diagnostic_rejected_int8'],str(base/'model.int8.tflite.rejected.tflite'))
if __name__=='__main__': unittest.main()
