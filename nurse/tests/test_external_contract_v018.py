"""External endpoint contract v0.1.8: no implicit engine fallbacks."""
import contextlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'src'
sys.path.insert(0,str(SRC))
from nurse.config import read_brain
from nurse.uci import Nurse

class Contract(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'brains.json'
    def tearDown(self):self.temp.cleanup()
    def read(self,cfg):
        self.path.write_text(json.dumps({'brains':{'picoSargon':cfg}}),encoding='utf-8')
        return read_brain(self.path,'picoSargon')
    def test_url_hostname(self):
        cfg=self.read({'type':'external','url':'picosargon.local:6110','ELO':1000})
        self.assertEqual((cfg['ipaddress'],cfg['port']),('picosargon.local',6110))
        self.assertEqual(cfg['_type'],'external')
    def test_legacy_player_without_type_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'type obligatorio'):
            self.read({'player':'external','evaluator':'null','url':'picosargon.local:6110'})
    def test_fields_equivalent(self):
        cfg=self.read({'type':'external','ipaddress':'picosargon.local','port':6110})
        self.assertEqual(cfg['port'],6110)
    def test_matching_both(self):
        cfg=self.read({'type':'external','url':'picosargon.local:6110','ipaddress':'picosargon.local','port':6110})
        self.assertEqual(cfg['port'],6110)
    def test_ipv6_url(self):
        cfg=self.read({'type':'external','url':'[::1]:6110'})
        self.assertEqual((cfg['ipaddress'],cfg['port']),('::1',6110))
    def test_missing_destination_fails(self):
        for bad in ({'type':'external'}, {'type':'external','player':'external','evaluator':'null'}):
            with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'sin destino TCP'):
                self.read(bad)
    def test_partial_address_fails(self):
        for cfg in ({'type':'external','ipaddress':'x'}, {'type':'external','port':6110}):
            with self.subTest(cfg=cfg),self.assertRaises(ValueError):self.read(cfg)
    def test_conflict_fails(self):
        with self.assertRaisesRegex(ValueError,'contradictorios'):
            self.read({'type':'external','url':'x:6110','ipaddress':'y','port':6110})
    def test_bad_url_fails(self):
        for url in ('abc','x:0','x:65536','http://x:6110','x:6110/path','x:abc','x:6110?q=1'):
            with self.subTest(url=url),self.assertRaises(ValueError):self.read({'type':'external','url':url})
    def test_no_external_fallback_to_uci(self):
        with self.assertRaisesRegex(ValueError,'sin destino TCP'):
            self.read({'player':'external','type':'external','evaluator':'null','args':['-x']})
    def test_handshake_to_real_tcp_socket(self):
        server=socket.socket();server.bind(('127.0.0.1',0));server.listen(1)
        port=server.getsockname()[1];received=[]
        def serve():
            try:
                client,_=server.accept();client.settimeout(3)
                with client:
                    incoming=client.makefile('r',encoding='utf-8')
                    for line in incoming:
                        cmd=line.strip();received.append(cmd)
                        if cmd=='uci':client.sendall(b'id name picoSargon MOCK\nuciok\n')
                        elif cmd=='isready':client.sendall(b'readyok\n')
                        elif cmd=='quit':break
            finally:server.close()
        th=threading.Thread(target=serve,daemon=True);th.start()
        self.read({'type':'external','url':f'127.0.0.1:{port}','timeout':3000})
        with contextlib.redirect_stderr(io.StringIO()):
            n=Nurse(self.path,'picoSargon',io.StringIO())
            n._ensure()
            self.assertIsNotNone(n.transport.sock)
            self.assertTrue(n.transport.wire_uci)
            n._drop_transport()
        self.assertIn('uci',received)
        self.assertIn('isready',received)
        th.join(timeout=4)
    def test_unreachable_fails_before_uciok(self):
        s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
        self.read({'type':'external','url':f'127.0.0.1:{port}','timeout':500})
        env=os.environ.copy();env['PYTHONPATH']=str(SRC)+os.pathsep+env.get('PYTHONPATH','')
        proc=subprocess.run([sys.executable,'-u','-m','nurse.uci','--brains',str(self.path),'--id','picoSargon'],input='uci\nisready\n',capture_output=True,text=True,timeout=5,env=env)
        self.assertNotEqual(proc.returncode,0)
        self.assertNotIn('uciok',proc.stdout)
        self.assertNotIn('readyok',proc.stdout)
        self.assertIn('no se pudo conectar',proc.stderr)

if __name__=='__main__':unittest.main()
