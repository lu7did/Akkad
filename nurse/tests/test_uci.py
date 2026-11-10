import unittest, tempfile,os,sys,json,subprocess,pathlib,threading,time,socket,contextlib,io
ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=ROOT/'src'
FIX=ROOT/'tests'/'fake_uci.py'
ENV=os.environ.copy();ENV['PYTHONPATH']=str(SRC)+os.pathsep+ENV.get('PYTHONPATH','')
PLATFORM='windows' if os.name=='nt' else 'macOS' if sys.platform=='darwin' else 'debian'

class NurseIntegration(unittest.TestCase):
    def profile(self,cfg):
        d=tempfile.TemporaryDirectory()
        path=pathlib.Path(d.name)/'brains.json'
        path.write_text(json.dumps({'brains':{'test':cfg}}),encoding='utf8')
        return d,path
    def test_exec_uci_bestmove(self):
        d,path=self.profile({'type':'uci','player':{PLATFORM:sys.executable},'args':['-u',str(FIX)],'evaluator':'null','timeout':3000,'ELO':500})
        try:
            p=subprocess.Popen([sys.executable,'-u','-m','nurse.uci','--brains',str(path),'--id','test'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=ENV)
            stdout,stderr=p.communicate('uci\nisready\nposition startpos\ngo movetime 1000\n',timeout=8)
            # EOF triggers shutdown, so complete search may not be observed.
            self.assertIn('uciok',stdout)
            self.assertIn('readyok',stdout)
            self.assertNotIn('Fake UCI started',stdout)
            self.assertIn('Fake UCI started',stderr)
            self.assertEqual(p.returncode,0,stderr)
        finally:d.cleanup()
    def test_engine_persistent_and_search(self):
        d,path=self.profile({'type':'uci','player':{PLATFORM:sys.executable},'args':['-u',str(FIX)],'evaluator':'null','timeout':3000})
        try:
            from nurse.uci import Nurse
            out=io.StringIO();n=Nurse(path,'test',out)
            n.dispatch('uci');n.dispatch('isready')
            n.dispatch('position startpos');n.dispatch('go movetime 500')
            n.search.join(timeout=5)
            self.assertIsNone(n.search)
            self.assertIn('bestmove e2e4',out.getvalue())
            pid=n.transport.proc.pid
            n.dispatch('go movetime 200');n.search.join(timeout=5)
            self.assertEqual(pid,n.transport.proc.pid)
            self.assertEqual(out.getvalue().count('bestmove e2e4'),2)
            n._drop_transport()
        finally:d.cleanup()
    def test_unknown_brain_fails_fast(self):
        d,path=self.profile({'type':'nurse','player':'sargon.py','evaluator':'classic.py'})
        try:
            from nurse.config import read_brain
            with self.assertRaisesRegex(ValueError,'desconocido'):read_brain(path,'missing')
        finally:d.cleanup()
    def test_reject_uci_evaluator(self):
        d,path=self.profile({'type':'uci','player':{PLATFORM:sys.executable},'evaluator':'classic'})
        try:
            from nurse.config import read_brain
            with self.assertRaisesRegex(ValueError,'evaluator=null'):read_brain(path,'test')
        finally:d.cleanup()
    def test_player_id_version_without_chess(self):
        for module in ('sargon','sargon_plus','random','doc','microchess','cerebrum','keras','alphazero','bellman'):
            r=subprocess.run([sys.executable,'-m','nurse.players.'+module,'--version'],capture_output=True,text=True,env=ENV,timeout=6)
            self.assertEqual(r.returncode,0,(module,r.stderr))
            self.assertIn('0.1.4',r.stdout)
    def test_tcp_startup_failure(self):
        d,path=self.profile({'type':'external','ipaddress':'127.0.0.1','port':1,'retry':.5})
        try:
            from nurse.uci import Nurse
            from nurse.transport import TransportError
            n=Nurse(path,'test',io.StringIO())
            with self.assertRaises(TransportError):n._ensure()
            self.assertGreater(n.next_retry,time.monotonic())
        finally:d.cleanup()

if __name__=='__main__':unittest.main()
