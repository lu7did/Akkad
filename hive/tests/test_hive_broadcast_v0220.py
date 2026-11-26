"""Discovery math, simulated calibration and real loopback TCP/UDP framing."""
import contextlib
import io
import json
import math
import pathlib
import socket
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch
try:
    import chess
except ImportError:
    sys.modules['chess']=types.SimpleNamespace(STARTING_FEN='rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
import hive
import hive_beacon as beacon


def cfg(master=False, node='a'*32):
    return dict(name='test',master=master,node_id=node,broadcast=5,tcp_port=6250,udp_port=6251,
                advertise_ip='127.0.0.1',qdepth=2,engines=[],recalibration_min=30,recalibration_max=60,
                retry_seconds=5,connect_timeout_s=1,handshake_timeout_s=1)


def ep(name,ms,lo=0,hi=1,remote=False):
    spec=dict(name=name,type='tcp' if remote else 'uci',kmin=lo,kmax=hi)
    if remote:spec['discovered_id']='b'*32
    e=hive.Endpoint(spec,static=not remote);e.last_test_ms=ms
    e.transport=types.SimpleNamespace(dead=threading.Event(),close=lambda:None)
    return e


def adv(master=False,seq=1,event='STARTUP',node='b'*32,engines=None):
    return dict(protocol='HIVE',version=1,event=event,node_id=node,boot_id='c'*32,sequence=seq,
                name='remote',ip='127.0.0.1',tcp_port=6250,master=master,
                engines=[dict(name='stockfish',effective_ms=2)] if engines is None else engines)


def wait(pred,seconds=2):
    end=time.monotonic()+seconds
    while not pred():
        if time.monotonic()>end:raise AssertionError('timeout')
        time.sleep(.01)


class Broadcast(unittest.TestCase):
    def setUp(self):
        self.output=io.StringIO();cm=contextlib.redirect_stderr(self.output);cm.__enter__();self.addCleanup(cm.__exit__,None,None,None)
    def registry(self,*es):
        r=hive.Registry(cfg(True),'a'*32);r.items={e.name:e for e in es};r.starting=False;r.last_full_calibration=time.monotonic();r.weights(force=True);return r
    def test_conservation(self):
        es=[ep('a',2,.45,.8),ep('b',1000,.45,.8),ep('c',10,.1,.8)]
        times=beacon.effective_times(es,hive.Registry.effective_priorities(es))
        self.assertAlmostEqual(sum(1/e['effective_ms'] for e in times),sum(1/e.last_test_ms for e in es))
        self.assertAlmostEqual(beacon.aggregate_ms(times),1000/601)
    def test_zero_share(self):
        es=[ep('a',2,.5,.8),ep('b',3,.5,.8),ep('c',1)]
        self.assertIsNone(beacon.effective_times(es,hive.Registry.effective_priorities(es))[2]['effective_ms'])
    def test_local_only_snapshot(self):
        r=self.registry(ep('local',4),ep('remote',.5,remote=True))
        self.assertAlmostEqual(r.advertised_engines()[0]['effective_ms'],4)
        self.assertEqual(len(r.advertised_engines()),1)
        self.assertAlmostEqual(r.allocation['remote'],8/9)
    def test_beacon_update_and_empty(self):
        remote=ep('discovered-'+'b'*32,2,remote=True)
        r=self.registry(ep('local',4,.2,1),remote)
        old=remote.transport
        with patch.object(r,'test') as probe:
            r.discovered(adv(engines=[dict(name='a',effective_ms=1),dict(name='b',effective_ms=1)]))
            self.assertEqual(remote.last_test_ms,.5);self.assertIs(remote.transport,old)
            self.assertAlmostEqual(r.allocation[remote.name],.8*8/9)
            r.discovered(adv(engines=[]));self.assertNotIn(remote.name,r.allocation)
            self.assertIs(remote.transport,old);probe.assert_not_called()
    def test_periodic_no_remote_probe(self):
        local=ep('local',4);remote=ep('remote',2,remote=True);r=self.registry(local,remote)
        with patch.object(r,'test') as probe:
            r.periodic(r.last_full_calibration+1801);probe.assert_called_once_with(local)
    def test_role_matrix(self):
        for master in (False,True):
            r=hive.Registry(cfg(master),'a'*32)
            with patch('hive.threading.Thread') as thread:
                r.discovered(adv(master=True));self.assertFalse(r.items)
                r.discovered(adv());self.assertEqual(bool(r.items),master)
                self.assertEqual(thread.call_count,int(master))
    def test_beacon_validation_and_duplicate(self):
        r=self.registry(ep('local',4));d=hive.Discovery(cfg(True),r,'a'*32)
        with patch.object(r,'discovered') as received:
            payload=json.dumps(adv()).encode();self.assertTrue(d.receive(payload));self.assertFalse(d.receive(payload));received.assert_called_once()
            self.assertFalse(d.receive(json.dumps(adv(node='a'*32)).encode()))
            self.assertTrue(d.receive(json.dumps(adv(master=True,node='e'*32)).encode()));self.assertIn('MULTIPLE MASTERS',self.output.getvalue())
            for bad in (0,-1,float('inf'),True,'3'):
                with self.assertRaises(ValueError):beacon.decode(json.dumps(adv(engines=[dict(name='a',effective_ms=bad)])).encode())
    def test_real_udp_datagram(self):
        r=self.registry(ep('local',4));d=hive.Discovery(cfg(True),r,'a'*32)
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as rx, socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as tx:
            rx.bind(('127.0.0.1',0));rx.settimeout(1)
            tx.sendto(json.dumps(adv()).encode(),rx.getsockname());data,_=rx.recvfrom(65535)
            with patch.object(r,'discovered') as received:
                self.assertTrue(d.receive(data));received.assert_called_once()
            tx.sendto(d.announce('RESPONSE'),rx.getsockname());data,_=rx.recvfrom(65535)
            self.assertEqual(beacon.decode(data)['event'],'RESPONSE')

    def test_yaml_new_fields(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'hive.yml';p.write_text('engines: [{name: a, type: uci, path: test.exe}]\nmaster: true\nbroadcast: 2.5\nbroadcast_port: 6261\n')
            c=hive.load_config(p);self.assertTrue(c['master']);self.assertEqual(c['broadcast'],2.5);self.assertEqual(c['udp_port'],6261)
            p.write_text('engines: [{name: a, type: uci, path: test.exe}]\nbroadcast: true\n')
            with self.assertRaises(ValueError):hive.load_config(p)
    def test_actual_tcp_master_exclusive_and_normal_uci(self):
        h=hive.Hive(cfg(False,'b'*32));h.discovery=hive.Discovery(h.cfg,h.registry,h.node_id)
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();self.addCleanup(listener.close)
        threads=[];clients=[]
        def client():
            c=socket.create_connection(listener.getsockname(),timeout=1);clients.append(c)
            s,a=listener.accept();t=threading.Thread(target=h.tcp_client,args=(s,a),daemon=True);threads.append(t);t.start();return c
        def exchange(c,line):
            c.sendall((line+'\n').encode());data=b''
            while b'uciok\n' not in data:
                chunk=c.recv(4096)
                if not chunk:break
                data+=chunk
            return data
        with patch.object(hive.chess,'Board',create=True,return_value=object()):
            try:
                a=client();self.assertIn(b'uciok',exchange(a,'uci (master)'));self.assertIsNotNone(h.master_session)
                b=client();self.assertEqual(exchange(b,'uci (master)'),b'');self.assertIn('master connection rejected',self.output.getvalue())
                c=client();self.assertIn(b'uciok',exchange(c,'uci'));self.assertIsNotNone(h.master_session)
                a.close();wait(lambda:h.master_session is None);self.assertTrue(h.discovery.changed.is_set())
                e=client();self.assertIn(b'uciok',exchange(e,'uci (master)'))
                e.close();wait(lambda:h.master_session is None)
                h.cfg['master']=True;f=client();self.assertEqual(exchange(f,'uci (master)'),b'')
            finally:
                for c in clients:c.close()
                for t in threads:t.join(2)
    def test_actual_endpoint_handshake_and_no_probe(self):
        subordinate=hive.Hive(cfg(False,'b'*32));r=self.registry(ep('local',4));listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();self.addCleanup(listener.close)
        advert=adv();advert['tcp_port']=listener.getsockname()[1]
        with patch.object(hive.chess,'Board',create=True,return_value=object()),patch.object(r,'test') as probe:
            r.discovered(advert);s,a=listener.accept();t=threading.Thread(target=subordinate.tcp_client,args=(s,a),daemon=True);t.start()
            try:
                wait(lambda:'discovered-'+'b'*32 in r.allocation)
                self.assertIsNotNone(subordinate.master_session);probe.assert_not_called()
                self.assertAlmostEqual(r.allocation['discovered-'+'b'*32],2/3)
            finally:r.stop();t.join(2)
    def test_published_beacon_snapshot(self):
        a=ep('a',4);r=self.registry(a);d=hive.Discovery(cfg(True),r,'a'*32)
        old=beacon.decode(d.announce('STARTUP'));a.last_test_ms=8;r.calibrating=True;r.weights()
        during=beacon.decode(d.announce('HEARTBEAT'));self.assertEqual(old['engines'],during['engines'])
        r.weights(force=True);after=beacon.decode(d.announce('UPDATE'));self.assertEqual(after['engines'][0]['effective_ms'],8)
        self.assertTrue(old['master']);self.assertGreater(after['sequence'],old['sequence'])

if __name__=='__main__':unittest.main()
