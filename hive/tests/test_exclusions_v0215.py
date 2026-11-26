import contextlib, importlib.util, io, sys, threading, types, unittest
from pathlib import Path
try:
    import chess
except ImportError:
    sys.modules['chess']=types.ModuleType('chess')
spec=importlib.util.spec_from_file_location('hive_under_test',Path(__file__).resolve().parents[1]/'src/hive.py')
h=importlib.util.module_from_spec(spec);sys.modules[spec.name]=h;spec.loader.exec_module(h)
class Exclusions(unittest.TestCase):
    def test_claim_reasons(self):
        names=['ok','busy','reserved','dead','offline','connecting']
        r=h.Registry({'engines':[{'name':n,'kmin':.1} for n in names]},'test')
        for n in names[:4]:r.items[n].transport=types.SimpleNamespace(dead=threading.Event())
        r.items['busy'].busy=True;r.items['reserved'].reserved=True;r.items['dead'].transport.dead.set();r.items['connecting'].connecting=True
        d={};self.assertEqual([e.name for e in r.claim(d)],['ok'])
        self.assertEqual({n:v[1] for n,v in d.items()},dict(busy='BUSY',reserved='RESERVED',dead='DEAD_TRANSPORT',offline='DISCONNECTED',connecting='CONNECTING'))
        self.assertTrue(r.items['ok'].reserved)
        r.release(r.items['ok']);self.assertEqual([e.name for e in r.claim()],['ok'])
    def test_levels(self):
        old=h._TELEMETRY_VERBOSE
        try:
            for level in (0,1,2):
                h._TELEMETRY_VERBOSE=level
                buf=io.StringIO()
                with contextlib.redirect_stderr(buf):h.report_exclusions('test',{'picoSargon':(.1,'BUSY')})
                self.assertEqual('reason=BUSY' in buf.getvalue(),level>=1)
        finally:h._TELEMETRY_VERBOSE=old
if __name__=='__main__':unittest.main()
