"""Telemetry regression tests: stderr only and stable aligned markers."""
import contextlib
import io
import importlib.util
import pathlib
import unittest
from unittest import mock

PATH = pathlib.Path(__file__).resolve().parents[1] / 'src' / 'hive.py'
spec = importlib.util.spec_from_file_location('hive_telemetry_under_test', PATH)
hive = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = hive
spec.loader.exec_module(hive)

class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.old_width = hive._TELEMETRY_WIDTH
        self.old_verbose = hive._TELEMETRY_VERBOSE
        hive._TELEMETRY_WIDTH = 12
        hive._TELEMETRY_VERBOSE = True

    def tearDown(self):
        hive._TELEMETRY_WIDTH = self.old_width
        hive._TELEMETRY_VERBOSE = self.old_verbose

    def test_stderr_only_and_alignment(self):
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            hive.telemetry('⚙️', 'x', 'priority=0.4')
            hive.telemetry('⚙️', 'AlphaZero', 'priority=0.6')
        self.assertEqual(out.getvalue(), '')
        lines = err.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith('⚙️['))
        self.assertEqual(lines[0].index('priority'),lines[1].index('priority'))

    def test_wrapped_arguments(self):
        err=io.StringIO()
        with contextlib.redirect_stderr(err):
            hive.telemetry_args('AlphaZero', ['--cores','4','--weights','C:/'+'file'*40],width=74)
        lines=err.getvalue().splitlines()
        self.assertGreater(len(lines), 1)
        self.assertTrue(all('AlphaZero' in line for line in lines))

    def test_session_u_c_i_frames(self):
        class Fake:
            node_id='a'*32
            cfg={'name':'mock','qdepth':2}
        out=[]
        s=hive.Session(Fake(),out.append,'stdio')
        err=io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertTrue(s.command('isready'))
        self.assertEqual(out,['readyok'])
        self.assertIn('➡️[',err.getvalue())
        self.assertIn('⬅️[',err.getvalue())

    def test_equilibrium_not_repeated(self):
        class FakeEp:
            name='stockfish';transport=type('T',(),{'dead':__import__('threading').Event()})();priority=.4
        class FakeRegistry:
            lock=__import__('threading').RLock()
            last_equilibrium=None
            def snapshot(self):return [FakeEp()]
        reg=FakeRegistry()
        err=io.StringIO()
        with contextlib.redirect_stderr(err):
            hive.telemetry_priority(reg)
            hive.telemetry_priority(reg)
        self.assertEqual(err.getvalue().count('⚖️['),1)

if __name__=='__main__': unittest.main()
