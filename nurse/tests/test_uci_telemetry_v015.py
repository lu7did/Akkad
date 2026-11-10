import io,json,os,pathlib,sys,tempfile,threading,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
PLATFORM='windows' if os.name=='nt' else 'macOS' if sys.platform=='darwin' else 'debian'

class UciTelemetryTest(unittest.TestCase):
    def make(self,extra=None):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        target=pathlib.Path(tmp.name)/'brains.json'
        profile={'type':'uci','player':{PLATFORM:sys.executable},
                 'args':['-u',str(ROOT/'tests'/'fake_uci.py')],
                 'evaluator':'null','tmax':200,'timeout':3000}
        profile.update(extra or {})
        target.write_text(json.dumps({'brains':{'fishy':profile}}),encoding='utf-8')
        return target
    def test_generic_setoption_contract(self):
        from nurse.config import read_brain,parse_uci_options
        path=self.make({'uci_options':{'Skill Level':5,'UCI_LimitStrength':True,'Clear Hash':None}})
        self.assertEqual(read_brain(path,'fishy')['_uci_options'],
            [('Skill Level','5'),('UCI_LimitStrength','true'),('Clear Hash',None)])
        self.assertEqual(parse_uci_options([{'name':'Threads','value':2},{'name':'Clear Hash'}]),
            [('Threads','2'),('Clear Hash',None)])
        for invalid in ({'a':'value\ninjected'}, {'a':[]}, [1], {'name\nX':'foo'}):
            with self.assertRaises(ValueError):parse_uci_options(invalid)
    def test_subprocess_telemetry_and_real_uci_output(self):
        from nurse.uci import Nurse
        import nurse.transport as transport
        log=[];lock=threading.Lock()
        def capture(line):
            with lock:log.append(line)
        out=io.StringIO()
        n=Nurse(self.make({'uci_options':{'Skill Level':5,'Clear Hash':None}}),'fishy',out)
        with patch.object(transport,'log',capture):
            n.dispatch('uci');n.dispatch('setoption name Threads value 1')
            n.dispatch('isready')
            n.dispatch('position startpos');n.dispatch('go movetime 100')
            thread=n.search
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            n._drop_transport()
        whole='\n'.join(log)
        self.assertIn('⬅️ UCI stdout id name Nurse Fake Engine',whole)
        self.assertIn('⬅️ UCI stdout uciok',whole)
        self.assertIn('⬅️ UCI stdout readyok',whole)
        self.assertIn('⬅️ UCI stdout info depth',whole)
        self.assertIn('⬅️ UCI stdout bestmove e2e4',whole)
        self.assertIn('➡️ UCI stdin setoption name Skill Level value 5',whole)
        self.assertIn('➡️ UCI stdin setoption name Clear Hash',whole)
        self.assertIn('➡️ UCI stdin setoption name Threads value 1',whole)
        outval=out.getvalue()
        self.assertIn('uciok',outval)
        self.assertIn('readyok',outval)
        self.assertIn('bestmove e2e4',outval)
        self.assertNotIn('⬅️',outval)
    def test_option_rejected_for_python_player(self):
        from nurse.config import read_brain
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        path=pathlib.Path(tmp.name)/'brains.json'
        path.write_text(json.dumps({'brains':{'a':{'type':'nurse','player':'sargon.py','evaluator':'null','uci_options':{'Skill Level':4}}}}))
        with self.assertRaisesRegex(ValueError,'uci_options'):read_brain(path,'a')

if __name__=='__main__':unittest.main()
