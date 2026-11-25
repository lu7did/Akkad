import contextlib
import importlib.util
import io
import pathlib
import sys
import threading
import types
import unittest
from unittest.mock import Mock

# No board operations are needed in this scheduler/output regression.
try:
    import chess
except ImportError:
    sys.modules['chess'] = types.ModuleType('chess')
path = pathlib.Path(__file__).resolve().parents[1] / 'src' / 'hive.py'
spec = importlib.util.spec_from_file_location('hive_v0212', path)
hive = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hive
spec.loader.exec_module(hive)

class Output(unittest.TestCase):
    def test_search_output_all_levels(self):
        for level in (0, 1, 2):
            with self.subTest(level=level):
                hive._TELEMETRY_VERBOSE = level
                ep = Mock(name='worker')
                ep.name = 'worker'; ep.last_test_ms = 1; ep.busy = False
                def info(cp):
                    return dict(cp=cp, mate=None, bound='exact', depth=9, nodes=100, time=5)
                ep.analyze.return_value = hive.WorkResult('worker','e2e4',{'e2e4':info(42),'d2d4':info(-80)},5,nodes=100)
                registry = Mock()
                registry.claim.return_value = [ep]
                registry.snapshot.return_value = [ep]
                registry.effective_priorities.return_value = {'worker':1.0}
                session = object.__new__(hive.Session)
                session.hive = types.SimpleNamespace(registry=registry, stopped=threading.Event(),cfg={'search_grace_s':1})
                session.closed=False; session.stop=threading.Event(); session.label='client'
                wire=[]; session.emit=wire.append
                log=io.StringIO()
                with contextlib.redirect_stderr(log):
                    session._search('position startpos',['e2e4','d2d4'],9,2,1000)
                self.assertEqual(len(wire),2)
                self.assertRegex(wire[0],r'^info depth 9 score cp 42 nodes 100 time \d+ pv e2e4$')
                self.assertEqual(wire[1],'bestmove e2e4')
                self.assertEqual(log.getvalue().count(' multipv '),2 if level==2 else 0)
                self.assertEqual(log.getvalue().count('⬅️['),2)
                if level==2:
                    self.assertIn('ℹ️[',log.getvalue())

if __name__=='__main__': unittest.main()
