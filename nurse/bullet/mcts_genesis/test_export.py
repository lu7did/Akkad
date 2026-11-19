import tempfile,random,struct,unittest
from pathlib import Path
from mcts_export import *
from mcts_audit import audit,predict

class ExportTests(unittest.TestCase):
    def test_contract_and_transpose(self):
        a=[0.0]*TOTAL
        # Embedding feature 7, neuron 4: raw and output both feature-major.
        a[7*16+4]=.125
        off=780*16+16
        # Rust FROM matrix 64 rows x 16 columns, column-major.
        a[off+4*64+7]=.25
        q,sc=quantize(a)
        self.assertEqual(q['W_INPUT'][7*16+4],127)
        self.assertEqual(q['W_FROM'][7*16+4],127)
        data=encode(q,sc)
        self.assertEqual(len(data),14580)
        qm,sm=decode(data)
        self.assertEqual(qm,q)
        self.assertAlmostEqual(sm['W_INPUT'],sc['W_INPUT'],places=10)
    def test_end_to_end_synthetic(self):
        rng=random.Random(7)
        x=[rng.uniform(-.06,.06) for _ in range(TOTAL)]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);raw=p/'raw.bin'
            raw.write_bytes(struct.pack('<%df'%TOTAL,*x))
            q,s=quantize(load_raw(raw));binfile=p/'test.bin';binfile.write_bytes(encode(q,s))
            report=audit(binfile,raw)
            self.assertEqual(report['max_prediction_difference'],0)
    def test_corruption(self):
        q,s=quantize([.01]*TOTAL)
        d=bytearray(encode(q,s));d[0]=0
        with self.assertRaises(ValueError):decode(d)

if __name__=='__main__':unittest.main()
