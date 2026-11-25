import importlib.util, pathlib, sys, types, unittest, threading
from unittest.mock import patch
try:
    import chess
except ImportError:
    sys.modules['chess']=types.ModuleType('chess')
spec=importlib.util.spec_from_file_location('hive_clock',pathlib.Path(__file__).resolve().parents[1]/'src'/'hive.py')
hive=importlib.util.module_from_spec(spec);sys.modules[spec.name]=hive;spec.loader.exec_module(hive)
class Clock(unittest.TestCase):
    def session(self,white=False):
        s=object.__new__(hive.Session);s.hive=types.SimpleNamespace(cfg=dict(depth=9,qdepth=2,timeout_ms=15000,search_grace_s=1.5));s.board=types.SimpleNamespace(turn=white,legal_moves=[types.SimpleNamespace(uci=lambda:'e7e5')]);s.position='position startpos moves e2e4';s.label='test';s.search_lock=threading.Lock();s.search_thread=None;s.stop=threading.Event();return s
    def go(self,cmd,white=False):
        with patch.object(hive.threading,'Thread') as t:
            self.session(white).go(cmd);return t.call_args.kwargs['args']
    def test_report(self):self.assertEqual(self.go('wtime 120000 btime 120000 winc 12000 binc 12000')[4],13000)
    def test_side(self):self.assertEqual(self.go('wtime 30000 btime 90000 winc 0 binc 0',True)[4],1000)
    def test_moves(self):self.assertEqual(self.go('wtime 100000 btime 100000 movestogo 10')[4],10000)
    def test_cap(self):self.assertEqual(self.go('btime 1000000 binc 100000')[4],15000)
    def test_low(self):self.assertEqual(self.go('btime 50 binc 12000')[4],40)
    def test_fixed(self):self.assertEqual(self.go('movetime 10000')[4:],(10000,None))
    def test_explicit(self):self.assertEqual(self.go('btime 100000 movetime 2000')[4],2000)
    def test_searchmoves(self):self.assertEqual(self.go('searchmoves e7e5 btime 30000')[1],['e7e5'])
    def test_bad(self):
        for cmd in ['btime -1','movestogo 0','wtime 1000','btime','wtime 1000 btime x']:
            with self.subTest(cmd=cmd),self.assertRaises(ValueError):self.go(cmd)
if __name__=='__main__':unittest.main()
