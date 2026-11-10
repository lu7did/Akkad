"""Fail closed when client and Nurse disagree about a TCP endpoint."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from nurse.config import brain_fingerprint,read_brain
from nurse.uci import main

class ExternalBindingTest(unittest.TestCase):
    def make(self,folder):
        p=Path(folder)/'brains.json'
        p.write_text(json.dumps({'brains':{'picoSargon':{'type':'external',
          'url':'picosargon.local:6110','timeout':1000,'tmax':1000}}}),encoding='utf-8')
        return p
    def test_fingerprint_stable_and_detects_change(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.make(d)
            a=brain_fingerprint(p,'picoSargon')
            self.assertEqual(a,brain_fingerprint(p,'picoSargon'))
            p.write_text(p.read_text().replace('6110','6200'))
            self.assertNotEqual(a,brain_fingerprint(p,'picoSargon'))
    def test_endpoint_mismatch_rejected_before_connect(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.make(d)
            with patch('nurse.uci.Nurse._ensure',side_effect=AssertionError('MUST NOT CONNECT')):
                self.assertEqual(2,main(['--brains',str(p),'--id','picoSargon',
                                        '--expect-endpoint','127.0.0.1:6200']))
    def test_fingerprint_mismatch_rejected_before_connect(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.make(d)
            with patch('nurse.uci.Nurse._ensure',side_effect=AssertionError('MUST NOT CONNECT')):
                self.assertEqual(2,main(['--brains',str(p),'--id','picoSargon',
                                         '--expect-brain-sha256','0'*64]))
    def test_correct_endpoint_not_forced_to_localhost(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.make(d)
            self.assertEqual(('picosargon.local',6110),
                             (read_brain(p,'picoSargon')['ipaddress'],read_brain(p,'picoSargon')['port']))
