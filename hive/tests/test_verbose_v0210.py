import contextlib
import importlib.util
import io
import pathlib
import queue
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

PATH = pathlib.Path(__file__).resolve().parents[1] / 'src' / 'hive.py'
spec = importlib.util.spec_from_file_location('hive_v0210', PATH)
hive = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hive
spec.loader.exec_module(hive)

class Verbosity(unittest.TestCase):
    def setUp(self):
        self.old = hive._TELEMETRY_VERBOSE
    def tearDown(self):
        hive._TELEMETRY_VERBOSE = self.old
    def test_levels(self):
        cases = [('➡️','go'),('⬅️','bestmove e2e4'),('⚙️','assigned 1/1'),('🧠','bestmove e2e4'),('✉️','go'),('📮','readyok'),('ℹ️','info depth 1')]
        for level, count in [(0,2),(1,4),(2,7)]:
            hive._TELEMETRY_VERBOSE=level
            stream=io.StringIO()
            with contextlib.redirect_stderr(stream):
                for symbol,line in cases:hive.telemetry(symbol,'engine',line)
            self.assertEqual(len(stream.getvalue().splitlines()),count)
    def test_config(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'hive.yml'
            for text,expected in [('{}',1),('verbose: 0',0),('verbose: 1',1),('verbose: 2',2),('verbose: false',0),('verbose: true',1)]:
                p.write_text(text)
                self.assertEqual(hive.load_config(p)['verbose'],expected)
            p.write_text('verbose: 3')
            with self.assertRaises(ValueError):hive.load_config(p)
    def test_cli_override(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'hive.yml';p.write_text('verbose: 0')
            with patch.object(hive,'Hive') as fake, patch.object(hive.logging,'basicConfig'):
                self.assertEqual(hive.main(['--hive',str(p),'--verbose=2']),0)
                self.assertEqual(fake.call_args.args[0]['verbose'],2)
    def test_worker_result_unchanged(self):
        lines=['info depth 9 multipv 1 score cp 42 nodes 100 time 10 nps 10000 pv e2e4','info depth 9 multipv 2 score cp -80 nodes 100 time 10 nps 10000 pv d2d4','bestmove e2e4 ponder e7e5']
        results=[]
        for level in (0,1,2):
            hive._TELEMETRY_VERBOSE=level
            ep=hive.Endpoint({'name':'test','type':'uci'})
            t=object.__new__(hive.Transport);t.name='test';t.timeout=1;t.q=queue.Queue();t.send=lambda line: hive.telemetry('✉️',t.name,line)
            for line in lines:t.q.put(line)
            ep.transport=t
            stream=io.StringIO()
            with contextlib.redirect_stderr(stream):
                r=ep.analyze('position startpos',['e2e4','d2d4'],9,None,1000)
            results.append((r.best,r.infos,r.nodes,r.nps,r.uci_time_ms))
            out=stream.getvalue()
            self.assertEqual(out.count('🧠['),int(level>=1))
            self.assertEqual(out.count('ℹ️['),2 if level==2 else 0)
            self.assertNotIn('📮',out)
            if level>=1:self.assertIn('bestmove e2e4 ponder e7e5 score cp 42',out)
        self.assertEqual(results[0],results[1]);self.assertEqual(results[1],results[2])
    def test_client_output_unchanged(self):
        for level in (0,1,2):
            hive._TELEMETRY_VERBOSE=level
            session=object.__new__(hive.Session);session.closed=False;session.label='client';out=[];session.emit=out.append
            with contextlib.redirect_stderr(io.StringIO()):session.send('info depth 9 score cp 42');session.send('bestmove e2e4')
            self.assertEqual(out,['info depth 9 score cp 42','bestmove e2e4'])

if __name__=='__main__':unittest.main()
