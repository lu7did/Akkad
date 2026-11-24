"""Regression for Hive v0.2.1 resource scheduling and recursive performance probe."""
import importlib.util
import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from test_v020 import hive, cfg, Server


class Changes(unittest.TestCase):
    def test_advertisement_includes_connected_engine_count(self):
        a,b=Server(),Server()
        try:
            c=cfg(a,b);r=hive.Registry(c,c['node_id'])
            for e in r.snapshot():r._connect_and_test(e)
            advert=json.loads(hive.Discovery(c,r,c['node_id']).announce())
            self.assertEqual(advert['engines'],2)
            r.stop()
        finally:a.close();b.close()

    def test_hive_subtree_probe_uses_advertised_parallel_jobs(self):
        remote='0'*32
        a=Server(nodeid=remote,slow=.12)
        try:
            c=cfg();r=hive.Registry(c,c['node_id'])
            advert=dict(kind='HIVE_ADVERTISE',node_id=remote,name='remote',ip='127.0.0.1',port=a.port,engines=3)
            r.discovered(advert)
            end=time.monotonic()+5
            while time.monotonic()<end:
                e=r.items.get('discovered-'+remote)
                if e and e.last_test_ms is not None:break
                time.sleep(.02)
            else:self.fail('remote Hive probe not completed')
            probes=[s for s in a.commands if s.startswith('go ')];self.assertEqual(len(probes),3)
            self.assertLess(e.last_test_ms,115, 'parallel per-move time should be below one job wall time')
            self.assertEqual(e.test_nps,1500)
            r.stop()
        finally:a.close()

    def test_busy_tcp_waits_beyond_movetime_then_services_second_session(self):
        a=Server(slow=.3)
        try:
            c=cfg(a);c['timeout_ms']=100;c['search_grace_s']=1.0
            h=hive.Hive(c)
            for e in h.registry.snapshot():h.registry._connect_and_test(e)
            xout=[];yout=[]
            x=hive.Session(h,xout.append,'tcp-1');y=hive.Session(h,yout.append,'tcp-2')
            x.command('go depth 3 movetime 100 searchmoves e2e4')
            time.sleep(.04);begin=time.monotonic()
            y.command('go depth 3 movetime 100 searchmoves d2d4')
            x.search_thread.join(4);y.search_thread.join(4)
            self.assertFalse(x.search_thread.is_alive())
            self.assertFalse(y.search_thread.is_alive())
            self.assertGreater(time.monotonic()-begin,.45)
            self.assertEqual(xout[-1],'bestmove e2e4')
            self.assertEqual(yout[-1],'bestmove d2d4')
            h.registry.stop()
        finally:a.close()

    def test_concurrent_uci_sessions_spawn_local_process(self):
        # A standalone local mock UCI executable. Every subprocess has its own stdin/stdout.
        code='''import sys,time
for line in sys.stdin:
 line=line.strip()
 if line=='uci':print('id name mock local\\nuciok',flush=True)
 elif line=='isready':print('readyok',flush=True)
 elif line.startswith('go '):
  if 'searchmoves ' in line:
   move=line.split('searchmoves ',1)[1].split()[0]
   time.sleep(.25)
   print(f'info depth 3 score cp 18 nodes 123 time 250 nps 500 pv {move}',flush=True)
   print('bestmove '+move,flush=True)
 elif line=='quit':break
'''
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'mock_uci.py';source.write_text(code,encoding='utf-8')
            c=cfg();c['engines']=[dict(name='local',type='uci',path=sys.executable,args=str(source))]
            h=hive.Hive(c)
            ep=h.registry.snapshot()[0];h.registry._connect_and_test(ep)
            xout=[];yout=[]
            x=hive.Session(h,xout.append,'first');y=hive.Session(h,yout.append,'second')
            x.command('go depth 3 movetime 500 searchmoves e2e4')
            time.sleep(.03)
            y.command('go depth 3 movetime 500 searchmoves d2d4')
            x.search_thread.join(5);y.search_thread.join(5)
            self.assertFalse(x.search_thread.is_alive())
            self.assertFalse(y.search_thread.is_alive())
            self.assertEqual(xout[-1],'bestmove e2e4')
            self.assertEqual(yout[-1],'bestmove d2d4')
            clones=[ep for ep in h.registry.snapshot() if '#instance-' in ep.name]
            self.assertGreaterEqual(len(clones),1)
            h.registry.stop()

if __name__=='__main__':unittest.main(verbosity=2)
