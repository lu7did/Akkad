"""Nurse: platform CLI args (without legacy {network} substitution)."""
import io, json, os, pathlib, sys, tempfile, unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
PLATFORM='windows' if os.name=='nt' else 'macOS' if sys.platform=='darwin' else 'debian'

class PlatformArgsTest(unittest.TestCase):
    def make_brain(self, profile):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d=pathlib.Path(tmp.name)
        path=d/'brains.json'
        path.write_text(json.dumps({'brains':{'emma':profile}}),encoding='utf8')
        return path,d
    def test_platform_args_explicit_weights(self):
        from nurse.config import read_brain
        # Simulate the 3 OS paths without requiring their executables.
        for platform in ['windows','debian','macOS']:
            with self.subTest(platform=platform):
                path,base=self.make_brain({'type':'uci','evaluator':'null',
                    'player':{'windows':sys.executable,'debian':sys.executable,'macOS':sys.executable}})
                source=json.loads(path.read_text(encoding='utf8'))
                source['brains']['emma']['args']={
                    'windows':['--weights',str((base/'w.pb.gz').resolve()),'--backend','onnx-dml'],
                    'debian':['--weights',str((base/'d.pb.gz').resolve()),'--backend','eigen'],
                    'macOS':['--weights',str((base/'m.pb.gz').resolve()),'--backend','eigen']}
                path.write_text(json.dumps(source),encoding='utf8')
                for name in ('w.pb.gz','d.pb.gz','m.pb.gz'):(base/name).write_bytes(b'placeholder')
                with patch('nurse.config.platform_name',return_value=platform):
                    cfg=read_brain(path,'emma')
                self.assertEqual(cfg['_args'][1],str((base/('w.pb.gz' if platform=='windows' else 'd.pb.gz' if platform=='debian' else 'm.pb.gz')).resolve()))
                self.assertEqual(cfg['_args'][3],'onnx-dml' if platform=='windows' else 'eigen')
    def test_backwards_compatible_list(self):
        from nurse.config import read_brain
        path,_=self.make_brain({'type':'uci','evaluator':'null','player':{PLATFORM:sys.executable},'args':['-u','worker.py']})
        self.assertEqual(read_brain(path,'emma')['_args'],['-u','worker.py'])
    def test_bad_config(self):
        from nurse.config import read_brain
        base={'type':'uci','evaluator':'null','player':{PLATFORM:sys.executable}}
        for kwargs in [{'args':['--weights','{network}']},{'network':{PLATFORM:'weights.pb.gz'}},{'args':{PLATFORM:'bad'}}]:
            with self.subTest(kwargs=kwargs):
                path,_=self.make_brain(base|kwargs)
                with self.assertRaises(ValueError):read_brain(path,'emma')
    def test_process_argv_integration(self):
        from nurse.uci import Nurse
        fake=str(ROOT/'tests'/'fake_uci.py')
        path,_=self.make_brain({'type':'uci','player':{PLATFORM:sys.executable},'evaluator':'null',
            'args':{PLATFORM:['-u',fake]},'tmax':200,'timeout':1000})
        n=Nurse(path,'emma',io.StringIO())
        n.dispatch('isready');n.dispatch('position startpos');n.dispatch('go movetime 100')
        worker=n.search
        worker.join(timeout=4)
        self.assertFalse(worker.is_alive())
        self.assertIn('bestmove e2e4',n.out.getvalue())
        n._drop_transport()

if __name__=='__main__':unittest.main()
