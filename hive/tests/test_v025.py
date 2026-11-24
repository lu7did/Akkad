"""Regression tests for v0.2.5: latency vs effective assignment priority."""
import importlib.util
import pathlib
import unittest

MODULE_PATH=pathlib.Path(__file__).resolve().parents[1]/'src'/'hive.py'
spec=importlib.util.spec_from_file_location('hive_under_test_025',MODULE_PATH)
import sys
hive=importlib.util.module_from_spec(spec);sys.modules[spec.name]=hive;spec.loader.exec_module(hive)

class StubTransport:
    dead=type('D',(),{'is_set':lambda self:False})()

class PreferenceTests(unittest.TestCase):
    def test_priority_is_inverse_latency_even_if_k_increases(self):
        cfg={'engines':[{'name':'stockfish','type':'tcp','host':'localhost','port':1},
                        {'name':'alphazero','type':'tcp','host':'localhost','port':2},
                        {'name':'picoSargon','type':'tcp','host':'localhost','port':3}]}
        r=hive.Registry(cfg,'f'*32)
        for ep,ms in zip(r.snapshot(),[1,1508,1]):
            ep.transport=StubTransport();ep.last_test_ms=ms
        r.weights();a,b,c=r.snapshot()
        self.assertGreater(b.k,a.k)
        self.assertLess(b.priority,a.priority)
        self.assertAlmostEqual(sum(ep.priority for ep in r.snapshot()),1)
        self.assertAlmostEqual(b.k,1508/1510,places=5)
        self.assertAlmostEqual(a.priority,0.499834,places=5)

    def test_workresult_keeps_mcts_metadata_separate(self):
        r=hive.WorkResult('alphazero','e2e4',{'e2e4':{'cp':35}},1508,643,970,1508,1200)
        self.assertEqual(r.nps,643)
        self.assertEqual(r.simulations,1200)
        self.assertEqual(r.uci_time_ms,1508)

if __name__=='__main__':unittest.main()
