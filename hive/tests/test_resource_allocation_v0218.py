"""Pure scheduler and calibration lifecycle tests; no actual chess search."""
import contextlib
import io
import math
import pathlib
import random
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch
try:
    import chess
except ImportError:
    sys.modules['chess']=types.SimpleNamespace(STARTING_FEN='rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
import hive

def spec(name,lo=0,hi=1):return dict(name=name,type='uci',path='test.exe',kmin=lo,kmax=hi)
def ep(name,lo=0,hi=1,ms=1):
    e=hive.Endpoint(spec(name,lo,hi));e.last_test_ms=ms;e.transport=types.SimpleNamespace(dead=threading.Event(),close=lambda:None);return e

class Resources(unittest.TestCase):
    def setUp(self):
        self.output=io.StringIO();self.redirect=contextlib.redirect_stderr(self.output);self.redirect.__enter__();self.addCleanup(self.redirect.__exit__,None,None,None)
    def solve(self,*es):return hive.Registry.effective_priorities(es)
    def registry(self,es):
        r=hive.Registry(dict(engines=[],recalibration_min=30,recalibration_max=60,retry_seconds=5),'a'*32)
        r.items={e.name:e for e in es};r.starting=False;r.last_full_calibration=time.monotonic();r.weights(force=True);return r
    def test_inverse(self):
        k=self.solve(ep('fast',ms=1),ep('slow',ms=4));self.assertAlmostEqual(k['fast'],.8);self.assertAlmostEqual(k['slow'],.2)
    def test_minimum_then_residual(self):
        k=self.solve(ep('a',.2,1,1),ep('b',.3,1,3));self.assertAlmostEqual(k['a'],.575);self.assertAlmostEqual(k['b'],.425)
    def test_cap_redistribution(self):
        k=self.solve(ep('a',.1,.3,1),ep('b',.1,.4,2),ep('c',.1,1,10));self.assertAlmostEqual(k['a'],.3);self.assertAlmostEqual(k['b'],.4);self.assertAlmostEqual(k['c'],.3)
    def test_fixed_minima(self):
        self.assertEqual(self.solve(ep('a',.45,.8,1),ep('b',.45,.8,1500),ep('c',.1,.8,2)),{'a':.45,'b':.45,'c':.1})
    def test_fixed_maxima(self):
        k=self.solve(ep('a',0,.2,1),ep('b',0,.8,100));self.assertAlmostEqual(k['a'],.2);self.assertAlmostEqual(k['b'],.8)
    def test_invalid_constraints(self):
        for es in ([ep('a',.6,.8),ep('b',.6,.8)],[ep('a',0,.4),ep('b',0,.5)],[ep('a',.5,.5)],[ep('a',ms=0)],[]):
            with self.assertRaises(ValueError):self.solve(*es)
    def test_largest_remainder(self):
        self.assertEqual(hive.apportion_moves({'stockfish':.45,'alphazero':.45,'picoSargon':.1},27),{'stockfish':12,'alphazero':12,'picoSargon':3})
        for n in range(219):self.assertEqual(sum(hive.apportion_moves({'a':.45,'b':.45,'c':.1},n).values()),n)
    def test_random_feasible_allocations(self):
        rng=random.Random(21)
        for _ in range(500):
            n=rng.randint(2,12);v=[rng.random()+.001 for i in range(n)];total=sum(v);v=[x/total for x in v]
            es=[ep(str(i),x*rng.random(),x+(1-x)*rng.random(),10**rng.uniform(-3,5)) for i,x in enumerate(v)]
            k=self.solve(*es);self.assertAlmostEqual(math.fsum(k.values()),1,places=8)
            for e in es:self.assertGreaterEqual(k[e.name]+1e-9,e.kmin);self.assertLessEqual(k[e.name],e.kmax+1e-9)
    def test_incremental_loss_rejoin(self):
        a,b=ep('a',ms=1),ep('b',ms=4);r=self.registry([a,b]);old=r.last_full_calibration
        with patch.object(r,'test') as probe:
            b.drop();r.weights();self.assertEqual(r.allocation,{'a':1.0});probe.assert_not_called()
            b.transport=types.SimpleNamespace(dead=threading.Event(),close=lambda:None);b.last_test_ms=2;r.weights()
            self.assertAlmostEqual(r.allocation['a'],2/3);self.assertEqual(r.last_full_calibration,old);probe.assert_not_called()
    def test_reconnect_only_new_probe(self):
        a,b=ep('a',ms=1),ep('b',ms=4);r=self.registry([a,b]);b.drop()
        def connect(*args):b.transport=types.SimpleNamespace(dead=threading.Event(),close=lambda:None);return True
        with patch.object(b,'connect',side_effect=connect),patch.object(r,'test',side_effect=lambda e:setattr(e,'last_test_ms',2)) as probe:
            r._connect_and_test(b);probe.assert_called_once_with(b);self.assertAlmostEqual(r.allocation['a'],2/3)
    def test_periodic_idle_minimum(self):
        a,b=ep('a',ms=1),ep('b',ms=4);r=self.registry([a,b]);old=r.last_full_calibration
        with patch.object(r,'test',side_effect=lambda e:setattr(e,'last_test_ms',2)) as probe:
            r.periodic(old+1799);probe.assert_not_called();a.reserved=True;r.periodic(old+1800);probe.assert_not_called();a.reserved=False
            r.periodic(old+1801);self.assertEqual(probe.call_count,2);self.assertEqual(r.allocation,{'a':.5,'b':.5});self.assertFalse(r.calibration_pending)
    def test_forced_drain(self):
        a,b=ep('a'),ep('b');r=self.registry([a,b]);r.last_full_calibration-=3601;a.reserved=True
        with patch.object(r,'test') as probe:
            self.assertEqual(r.claim(),[]);self.assertTrue(r.calibration_pending);r.periodic();probe.assert_not_called()
            r.release(a);r.periodic();self.assertEqual(probe.call_count,2);self.assertFalse(r.calibration_pending)
            self.assertEqual(len(r.claim()),2)
    def test_idle_only_no_forced_barrier(self):
        a,b=ep('a'),ep('b');r=self.registry([a,b]);r.config['recalibration_max']=-1;r.last_full_calibration-=86400;a.reserved=True
        with patch.object(r,'test') as probe:
            r.periodic();probe.assert_not_called();self.assertFalse(r.calibration_pending)
            claimed=r.claim();self.assertEqual([e.name for e in claimed],['b']);r.release(b);r.release(a)
            r.periodic();self.assertEqual(probe.call_count,2);self.assertFalse(r.calibration_pending)
    def test_no_partial_publication(self):
        a,b=ep('a',ms=1),ep('b',ms=4);r=self.registry([a,b]);old=r.allocation.copy();r.last_full_calibration-=1900
        def probe(e):
            e.last_test_ms=2;r.weights();self.assertEqual(r.allocation,old);self.assertEqual(r.claim(),[])
        with patch.object(r,'test',side_effect=probe):r.periodic()
        self.assertEqual(r.allocation,{'a':.5,'b':.5})
    def test_runtime_infeasible(self):
        a,b=ep('a',0,.6),ep('b',0,.6);r=self.registry([a,b]);b.drop();r.weights();self.assertTrue(r.allocation_error);self.assertEqual(r.claim(),[])
    def test_yaml_defaults_and_errors(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'hive.yml';p.write_text('engines:\n  - {name: a, type: uci, path: a.exe}\n')
            cfg=hive.load_config(p);self.assertEqual((cfg['recalibration_min'],cfg['recalibration_max']),(30,60));self.assertEqual((cfg['engines'][0]['kmin'],cfg['engines'][0]['kmax']),(0,1))
            p.write_text('engines:\n  - {name: a, type: uci, path: a.exe}\nrecalibration_max: -1\n');self.assertEqual(hive.load_config(p)['recalibration_max'],-1)
            for extra in ('recalibration_max: -2\n','recalibration_min: 61\n','recalibration_max: 0\n','engines: []\n'):
                p.write_text('engines:\n  - {name: a, type: uci, path: a.exe}\n'+extra)
                with self.assertRaises(ValueError):hive.load_config(p)
    def test_startup_infeasible_active_set(self):
        r=self.registry([ep('a',0,.6),ep('b',0,.6)]);r.starting=True;r.items['b'].drop()
        with patch.object(r,'_connect_and_test'):
            with self.assertRaises(ValueError):r.startup()
        self.assertTrue(r.starting)

if __name__=='__main__':unittest.main()
