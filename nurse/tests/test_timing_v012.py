"""Regression tests: tmax=search budget, timeout=communication, warmup=tmax."""
import io, json, os, pathlib, sys, tempfile, unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
PLATFORM='windows' if os.name=='nt' else 'macOS' if sys.platform=='darwin' else 'debian'

class Timing012(unittest.TestCase):
    def profile(self,cfg):
        d=tempfile.TemporaryDirectory()
        path=pathlib.Path(d.name)/'brains.json'
        path.write_text(json.dumps({'brains':{'test':cfg}}),encoding='utf8')
        self.addCleanup(d.cleanup)
        return path

    def test_default_separation_all_types(self):
        from nurse.config import read_brain
        for cfg in (
            {'type':'nurse','player':'random.py','evaluator':'null'},
            {'type':'uci','player':{PLATFORM:sys.executable},'evaluator':'null'},
            {'type':'external','ipaddress':'127.0.0.1','port':6200},
        ):
            with self.subTest(type=cfg['type']):
                got=read_brain(self.profile(cfg),'test')
                self.assertEqual(got['tmax'],15000)
                self.assertEqual(got['timeout'],30000)
                self.assertEqual(got['warmup_movetime'],got['tmax'])

    def test_timeout_cannot_change_search_budget(self):
        from nurse.uci import Nurse
        path=self.profile({'type':'uci','player':{PLATFORM:sys.executable},'evaluator':'null','timeout':70000,'tmax':1200})
        n=Nurse(path,'test',io.StringIO())
        self.assertEqual(n._bounded_go('go'),('go movetime 1200',1200))
        self.assertEqual(n._bounded_go('go movetime 9000'),('go movetime 1200',1200))
        self.assertEqual(n._bounded_go('go movetime 300'),('go movetime 300',300))
        self.assertEqual(n._bounded_go('go depth 5'),('go depth 5 movetime 1200',1200))
        self.assertEqual(n._bounded_go('go infinite'),('go movetime 1200',1200))

    def test_invalid_configs(self):
        from nurse.config import read_brain
        base={'type':'nurse','player':'random.py','evaluator':'null'}
        for bad in ({'tmax':0},{'timeout':-1},{'tmax':1000,'warmup_movetime':500}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                read_brain(self.profile(base|bad),'test')

    def test_external_process_receives_bounded_go(self):
        from nurse.uci import Nurse
        fixture=ROOT/'tests'/'fake_uci.py'
        path=self.profile({'type':'uci','player':{PLATFORM:sys.executable},'args':['-u',str(fixture)],
                           'evaluator':'null','tmax':350,'timeout':1000})
        n=Nurse(path,'test',io.StringIO())
        n.dispatch('isready')
        n.dispatch('position startpos')
        n.dispatch('go movetime 30000')
        worker=n.search
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertIn('bestmove e2e4',n.out.getvalue())
        n._drop_transport()

    def test_benchmark_has_shared_warmup_contract(self):
        content=(ROOT/'src'/'nurse'/'benchmark.py').read_text(encoding='utf8')
        self.assertIn('warmup_ms = effective_tmax',content)
        self.assertIn('bk_budget_ms = min(effective_tmax, args.bk_movetime * 1000)',content)
        self.assertNotIn("command += ['--tmax'",content)
        self.assertNotIn('warmup_ms = 1000 if',content)

if __name__=='__main__':unittest.main()
