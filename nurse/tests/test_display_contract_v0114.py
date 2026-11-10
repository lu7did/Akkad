"""Regression checks: no false engine names and no duplicate brain IDs."""
import json
import tempfile
import unittest
from pathlib import Path
from nurse.display import benchmark_engine_heading, format_external_tcp_line
from nurse.config import read_brains

class DisplayContractTests(unittest.TestCase):
    def test_external_tcp_compact_line(self):
        details = dict(requested='picosargon.local:6110', dns=['192.168.68.108'],
                       peer_ip='192.168.68.108', peer_port=6110,
                       local_ip='192.168.68.105', local_port=17516,
                       uci_name='picoSargon v0.2.12')
        self.assertEqual(format_external_tcp_line(details),
                         '   🌐 TCP picosargon.local:6110 DNS=[192.168.68.108] name=picoSargon v0.2.12')
        self.assertNotIn('conectado=', format_external_tcp_line(details))
    def test_external_displays_remote_name_not_profile_name(self):
        cfg = dict(type='external', player='external', evaluator='null')
        self.assertTrue(benchmark_engine_heading('picoSargon', cfg, 'Motor libre').startswith('Motor libre ('))
    def test_local_types_display_brain_id(self):
        for typ in ('uci','nurse'):
            cfg = dict(type=typ, player='AlphaZero', evaluator='null')
            self.assertTrue(benchmark_engine_heading('emma',cfg,'Otros').startswith('emma ('))
    def test_no_remote_name_is_informative_not_error(self):
        details=dict(requested='picosargon.local:6110',dns=['192.168.68.108'])
        self.assertIn('name=(no informado)',format_external_tcp_line(details))
    def test_duplicate_id_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'brains.json'
            p.write_text('{"brains":{"x":{"type":"uci"},"x":{"type":"external"}}}',encoding='utf8')
            with self.assertRaisesRegex(ValueError,'duplicada'):
                read_brains(p)

if __name__=='__main__':unittest.main()
