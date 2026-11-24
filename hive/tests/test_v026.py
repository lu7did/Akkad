"""Regresiones de reservas kmin, Hive v0.2.6."""
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import types
import unittest

try:
    import chess  # noqa
except ImportError:
    chess_stub=types.ModuleType('chess')
    chess_stub.STARTING_FEN='rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
    sys.modules['chess']=chess_stub

source=Path(__file__).resolve().parents[1]/'src'/'hive.py'
sp=importlib.util.spec_from_file_location('hive_v026_under_test',source)
hive=importlib.util.module_from_spec(sp)
sys.modules[sp.name]=hive
sp.loader.exec_module(hive)

class Alive:
    def is_set(self): return False
class Transport:
    dead=Alive()

def ep(name,ms,kmin=None):
    d={'name':name,'type':'tcp','host':'localhost','port':6230}
    if kmin is not None:d['kmin']=kmin
    e=hive.Endpoint(d);e.transport=Transport();e.last_test_ms=ms
    return e

class KminTests(unittest.TestCase):
    def priorities(self,*eps):
        p=hive.Registry.effective_priorities(list(eps))
        self.assertTrue(all(0<=x<=1 for x in p.values()))
        self.assertLessEqual(sum(p.values()),1+1e-12)
        return p

    def test_example_three_engines(self):
        p=self.priorities(ep('alpha',1508,.3),ep('stockfish',1,.3),ep('picosargon',2))
        self.assertAlmostEqual(p['alpha'],.3)
        self.assertAlmostEqual(p['stockfish'],.3)
        self.assertAlmostEqual(p['picosargon'],.4)

    def test_example_four_engines_performance(self):
        p=self.priorities(ep('alpha',1508,.3),ep('stockfish',1,.3),ep('pico1',2),ep('pico2',4))
        self.assertAlmostEqual(p['pico1'],.4*2/3)
        self.assertAlmostEqual(p['pico2'],.4/3)

    def test_no_minimum_legacy_behavior(self):
        p=self.priorities(ep('stock',1),ep('alpha',1508),ep('sargon',1))
        self.assertAlmostEqual(p['alpha'],(1/1508)/(2+1/1508))
        self.assertAlmostEqual(sum(p.values()),1)

    def test_no_unspecified_preserves_unallocated_fraction(self):
        p=self.priorities(ep('a',1,.3),ep('b',3,.3))
        self.assertAlmostEqual(sum(p.values()),.6)

    def test_zero_remaining_unconfigured_does_not_receive_work(self):
        p=self.priorities(ep('a',1,.6),ep('b',2,.4),ep('c',1))
        self.assertAlmostEqual(p['c'],0)

    def test_missing_engine_recomputes_on_subset(self):
        p=self.priorities(ep('a',1,.3),ep('c',3))
        self.assertAlmostEqual(p['a'],.3)
        self.assertAlmostEqual(p['c'],.7)

    def test_invalid_kmin_values(self):
        base={'name':'a','type':'uci','path':'nonexistent'}
        for bad in (-.1,1.1,'0.3',True,float('nan'),float('inf'),None):
            with self.subTest(bad=bad),tempfile.TemporaryDirectory() as d:
                path=Path(d)/'hive.yml'
                import yaml
                path.write_text(yaml.safe_dump({'engines':[dict(base,kmin=bad)]}))
                with self.assertRaisesRegex(ValueError,'kmin'):
                    hive.load_config(path)

    def test_sum_greater_than_one_fails_on_load(self):
        import yaml
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'hive.yml'
            path.write_text(yaml.safe_dump({'engines':[
                {'name':'a','type':'uci','path':'a.exe','kmin':.7},
                {'name':'b','type':'uci','path':'b.exe','kmin':.4}]}))
            with self.assertRaisesRegex(ValueError,'sum of engine kmin'):
                hive.load_config(path)

    def test_sum_one_allowed(self):
        import yaml
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'hive.yml'
            path.write_text(yaml.safe_dump({'engines':[
                {'name':'a','type':'uci','path':'a.exe','kmin':.7},
                {'name':'b','type':'uci','path':'b.exe','kmin':.3}]}))
            self.assertAlmostEqual(sum(x['kmin'] for x in hive.load_config(path)['engines']),1)

    def test_clone_has_no_inherited_minimum(self):
        source=hive.Endpoint({'name':'a','type':'uci','path':'a.exe','kmin':.3})
        self.assertEqual(source.kmin,.3)
        clone_spec=dict(source.spec)
        clone_spec.pop('kmin',None)
        clone=hive.Endpoint(clone_spec)
        self.assertIsNone(clone.kmin)

if __name__=='__main__':unittest.main()
