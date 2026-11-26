import tempfile, pathlib, threading, time, unittest, types
from unittest.mock import patch
from test_resource_allocation_v0218 import hive
import yaml

def spec():
    return dict(name='SF-LC0',type='team',members=[dict(name='sf',type='uci',path='sf.exe',reliability=.25),dict(name='lc',type='tcp',host='localhost',port=1234,reliability=.75)])

def load(s):
    with tempfile.TemporaryDirectory() as d:
        p=pathlib.Path(d)/'hive.yml';p.write_text(yaml.safe_dump(dict(engines=[s])))
        return hive.load_config(p)

def live(team):
    for m in team.members:m.transport=types.SimpleNamespace(dead=threading.Event(),close=lambda:None)
    team.transport=hive.TeamTransport(team.members)

def result(m,move,score,bound='exact'):
    return hive.WorkResult(m.name,move,{move:dict(cp=score,mate=None,depth=4,bound=bound)},5,200,1,5)

class TeamTests(unittest.TestCase):
    def test_valid_config(self):
        cfg=load(spec());r=hive.Registry(cfg,'a'*32)
        self.assertEqual(list(r.items),['SF-LC0']);self.assertEqual(len(r.items['SF-LC0'].members),2)
    def test_invalid_weights(self):
        for w in [-1,True,.5,float('nan'),None]:
            s=spec();s['members'][0]['reliability']=w
            with self.assertRaises(ValueError):load(s)
    def test_minimum_members(self):
        s=spec();s['members'].pop()
        with self.assertRaises(ValueError):load(s)
    def test_joint_moves(self):
        t=hive.TeamEndpoint(spec());live(t);barrier=threading.Barrier(2);calls=[]
        def run(m,score,position,moves,*args):
            calls.append((m.name,position,tuple(moves)));barrier.wait(1)
            return result(m,moves[0],score if moves[0]=='e2e4' else -score)
        for m,score in zip(t.members,[120,40]):m.analyze=lambda *a,m=m,score=score:run(m,score,*a)
        r=t.analyze('position startpos',['e2e4','d2d4'],4,2,1000)
        self.assertEqual(r.best,'e2e4');self.assertEqual(r.infos['e2e4']['cp'],60);self.assertEqual(r.infos['d2d4']['cp'],-60);self.assertEqual(r.nodes,4)
        self.assertEqual(sorted(calls),sorted((m,'position startpos',(move,)) for m in ['sf','lc'] for move in ['e2e4','d2d4']))
    def test_missing_exact(self):
        t=hive.TeamEndpoint(spec());live(t)
        for m,b in zip(t.members,['exact','lowerbound']):m.analyze=lambda p,ms,*a,m=m,b=b:result(m,ms[0],50,b)
        r=t.analyze('position startpos',['e2e4'],4,2,1000);self.assertEqual(r.infos,{});self.assertEqual(r.best,'0000')
    def test_dead_member(self):
        t=hive.TeamEndpoint(spec());live(t);t.members[1].transport.dead.set();self.assertFalse(t.available());t.drop();self.assertTrue(all(m.transport is None for m in t.members))
    def test_one_capacity(self):
        cfg=load(spec());r=hive.Registry(cfg,'a'*32);t=r.items['SF-LC0'];live(t);t.last_test_ms=100
        r.weights(force=True);self.assertEqual(r.allocation,{'SF-LC0':1});self.assertEqual(len(r.advertised_engines()),1);self.assertAlmostEqual(r.advertised_engines()[0]['effective_ms'],100)
    def test_cancel(self):
        t=hive.TeamEndpoint(spec());live(t);cancel=threading.Event();cancel.set()
        r=t.analyze('position startpos',['e2e4'],4,2,1000,cancel);self.assertEqual(r.best,'0000');self.assertFalse(t.busy)
    def test_joint_calibration(self):
        cfg=load(spec());r=hive.Registry(cfg,'a'*32);t=r.items['SF-LC0'];live(t)
        move=cfg['test']['move'];fen=cfg['test']['fen'];barrier=threading.Barrier(2)
        def run(m,p,ms,*args):
            barrier.wait(1);time.sleep(.025 if m.name=='sf' else .060)
            return result(m,ms[0],40)
        for m in t.members:m.analyze=lambda *a,m=m:run(m,*a)
        board=types.SimpleNamespace(legal_moves=[move],fen=lambda:fen)
        with patch.object(hive.chess,'Board',return_value=board,create=True),patch.object(hive.chess,'Move',types.SimpleNamespace(from_uci=lambda x:x),create=True):r.test(t)
        self.assertGreaterEqual(t.last_test_ms,60);self.assertEqual(len(r.items),1)
