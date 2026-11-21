"""INT8 interchange tests. Run: python -m unittest discover -s picoGen/tools/train/tests -p '*v0159.py'"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import exportGrumpyInt8 as exporter

class TestGrumpyInt8(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.model=self.root/'best.npy'
        rng=np.random.default_rng(101)
        self.weights=rng.normal(0,2,exporter.GENES).astype(np.float32)
        np.save(self.model,self.weights)
        self.metadata={
            'format':exporter.FP32_FORMAT,'dtype':'float32','file':'best.npy',
            'genes':exporter.GENES,'architecture':exporter.ARCH,
            'hidden_clip':32,'output_scale':1,
            'fixed_material':[100,300,300,500,900,0],'generation':300}
        (self.root/'best.active.json').write_text(json.dumps(self.metadata))

    def test_round_trip_exact(self):
        q,sc=exporter.quantize(self.weights)
        payload=exporter.build_image(q,sc)
        self.assertEqual(len(payload),1840)
        self.assertEqual(payload[:8],b'GRQ8FP01')
        q2,s2=exporter.parse_image(payload)
        np.testing.assert_array_equal(q,q2)
        np.testing.assert_array_equal(sc,s2)
        dq=exporter.dequantize(q2,s2)
        self.assertEqual(dq.shape,(1680,))
        self.assertTrue(np.isfinite(dq).all())
        self.assertLess(np.max(np.abs(self.weights-dq)),0.2)

    def test_reject_corrupt(self):
        q,sc=exporter.quantize(self.weights)
        payload=bytearray(exporter.build_image(q,sc))
        payload[-1]^=1
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            exporter.parse_image(bytes(payload))
        with self.assertRaises(ValueError):
            exporter.parse_image(bytes(payload[:-1]))

    def test_reject_wrong_model(self):
        self.metadata['genes']=12321
        (self.root/'best.active.json').write_text(json.dumps(self.metadata))
        with self.assertRaisesRegex(ValueError,'incompatible'):
            exporter.read_fp32(self.model)

    def test_cli_artifacts(self):
        b=self.root/'model.bin';h=self.root/'model.hpp';report=self.root/'report.json'
        exporter.main(['--in',str(self.model),'--bin',str(b),'--hpp',str(h),'--report',str(report)])
        self.assertEqual(len(b.read_bytes()),1840)
        self.assertIn('kImageBytes = 1840',h.read_text())
        self.assertEqual(json.loads(report.read_text())['binary_sha256'],__import__('hashlib').sha256(b.read_bytes()).hexdigest())

    def test_cpp_inference_equivalence(self):
        if shutil.which('g++') is None:
            self.skipTest('g++ not installed')
        b=self.root/'model.bin';h=self.root/'model.hpp'
        exporter.main(['--in',str(self.model),'--bin',str(b),'--hpp',str(h)])
        source=self.root/'verify.cpp'
        source.write_text('''#include "model.hpp"
#include <iostream>
#include <iomanip>
int main() {
  std::uint16_t f[2][64] = {};
  for(int s=0;s<2;s++)for(int i=0;i<32;i++)f[s][i]=(s*31+i*7)%192;
  std::cout<<std::setprecision(12)<<picogen_grumpy_int8::evaluate(f,32,3,300.f,-1);
}''')
        subprocess.run(['g++','-std=c++17','-Wall','-Werror',str(source),'-o',str(self.root/'verify')],check=True,capture_output=True)
        actual=float(subprocess.check_output([str(self.root/'verify')],text=True))
        q,s=exporter.parse_image(b.read_bytes())
        f=np.zeros((2,64),dtype=np.int32)
        for side in range(2):
            for i in range(32):f[side,i]=(side*31+i*7)%192
        reference=exporter.evaluate_numpy(exporter.dequantize(q,s),(f,32,3,300.,-1))
        self.assertLess(abs(actual-reference),0.001)

if __name__=='__main__':unittest.main()
