"""Offline transport/logic smoke; real legality requires python-chess installed."""
import importlib.util,io,json,socket,sys,tempfile,threading,time,types,unittest
from pathlib import Path
from contextlib import redirect_stdout

ROOT=Path(__file__).resolve().parents[1]
class Move:
    def __init__(self,u):self.u=u
    def uci(self):return self.u
    @classmethod
    def from_uci(cls,u):return cls(u)
    def __eq__(self,o):return isinstance(o,Move) and self.u==o.u
    def __hash__(self):return hash(self.u)
class Board:
    def __init__(self,*args):self.legal_moves=[Move(u) for u in ['e2e4','d2d4','g1f3','c2c4']]
    def push(self,m):pass
    def fen(self):return 'FAKE'
fake=types.ModuleType('chess');fake.Board=Board;fake.Move=Move;fake.STARTING_FEN='FAKE'
sys.modules['chess']=fake
spec=importlib.util.spec_from_file_location('hive_v020',ROOT/'src'/'hive.py')
hive=importlib.util.module_from_spec(spec);sys.modules[spec.name]=hive;spec.loader.exec_module(hive)

class Server:
    def __init__(self,nodeid=None,slow=0):
        self.sock=socket.socket();self.sock.bind(('127.0.0.1',0));self.sock.listen(8)
        self.port=self.sock.getsockname()[1];self.nodeid=nodeid;self.slow=slow;self.commands=[]
        self.shutdown=threading.Event()
        threading.Thread(target=self.run,daemon=True).start()
    def run(self):
        self.sock.settimeout(.2)
        while not self.shutdown.is_set():
            try:c,_=self.sock.accept()
            except socket.timeout:continue
            except OSError:return
            threading.Thread(target=self.conn,args=(c,),daemon=True).start()
    def conn(self,c):
        try:
            with c,c.makefile('r',encoding='utf-8') as f:
                for line in f:
                    line=line.strip();self.commands.append(line)
                    if line=='uci':
                        extra=('option name HiveNodeID type string default '+self.nodeid+'\n') if self.nodeid else ''
                        c.sendall(('id name mock\noption name QDepth type spin default 2 min 0 max 64\n'+extra+'uciok\n').encode())
                    elif line=='isready':c.sendall(b'readyok\n')
                    elif line.startswith('go '):
                        if self.slow:time.sleep(self.slow)
                        m=line.split('searchmoves ',1)[1].split();lines=''.join(
                            f'info depth 3 multipv {i} score cp {100-i} nodes 123 time 10 nps 500 pv {move}\n'
                            for i,move in enumerate(m,1))
                        c.sendall((lines+'bestmove '+m[0]+'\n').encode())
        except OSError:pass
    def close(self):self.shutdown.set();self.sock.close()

def cfg(*servers):
    return dict(name='Hive-test',node_id='f'*32,listen_ip='127.0.0.1',tcp_port=6250,udp_port=6251,
        broadcast=False,hive_network=False,broadcast_seconds=5,retry_seconds=1,connect_timeout_s=1,
        handshake_timeout_s=1,search_grace_s=1,depth=9,qdepth=9,timeout_ms=1000,verbose=False,
        engines=[dict(name=f'e{i}',type='tcp',host='127.0.0.1',port=s.port) for i,s in enumerate(servers)],
        test=dict(fen='FAKE',move='e2e4',depth=3,qdepth=2,movetime_ms=500))

class Tests(unittest.TestCase):
    def test_config_required(self):
        with self.assertRaises(ValueError):hive.load_config('/does-not-exist/hive.yml')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'hive.yml';p.write_text('engines: []\n',encoding='utf-8')
            self.assertEqual(hive.load_config(p)['tcp_port'],6250)
    def test_parse(self):
        info=hive.tokens_info('info depth 9 score cp -42 upperbound nodes 120 time 90 nps 1000 pv d2d4 d7d5')
        self.assertEqual((info['cp'],info['bound'],info['move']),(-42,'upperbound','d2d4'))
    def test_connection_probe_and_k(self):
        a,b=Server(),Server()
        try:
            c=cfg(a,b);registry=hive.Registry(c,c['node_id'])
            for ep in registry.snapshot():registry._connect_and_test(ep)
            self.assertEqual(len(registry.active()),2)
            self.assertAlmostEqual(sum(e.k for e in registry.active()),1,places=6)
            self.assertTrue(all(e.test_nps==500 for e in registry.active()))
            self.assertEqual(sum(e.test_nps for e in registry.active()),1000)
            registry.stop()
        finally:a.close();b.close()
    def test_partition_and_bestmove(self):
        a,b=Server(),Server()
        try:
            c=cfg(a,b);h=hive.Hive(c)
            for ep in h.registry.snapshot():h.registry._connect_and_test(ep)
            output=[];session=hive.Session(h,output.append,'test-session')
            session.command('position startpos')
            session.command('go depth 9 qdepth 4 movetime 500 searchmoves e2e4 d2d4 g1f3 c2c4')
            session.search_thread.join(3)
            self.assertFalse(session.search_thread.is_alive())
            go=[x for x in a.commands+b.commands if x.startswith('go ') and 'depth 9' in x]
            self.assertEqual(len(go),2)
            sets=[set(x.split('searchmoves ',1)[1].split()) for x in go]
            self.assertFalse(sets[0]&sets[1]);self.assertEqual(set.union(*sets),{'e2e4','d2d4','g1f3','c2c4'})
            self.assertEqual(sum(x.startswith('bestmove ') for x in output),1)
            self.assertEqual(sum(' multipv ' in x for x in output),4)
            h.registry.stop()
        finally:a.close();b.close()
    def test_isolated_session_positions(self):
        h=hive.Hive(cfg())
        a=[];b=[];x=hive.Session(h,a.append,'stdio');y=hive.Session(h,b.append,'tcp')
        x.command('position startpos moves e2e4')
        y.command('position startpos moves d2d4')
        self.assertNotEqual(x.position,y.position)
        x.command('quit');self.assertFalse(y.closed)
        y.command('isready');self.assertEqual(b[-1],'readyok')
    def test_cycle_order_guard(self):
        low='0'*32;high='f'*32
        a=Server(nodeid=high);b=Server(nodeid=low)
        try:
            c=cfg();ep1=hive.Endpoint(dict(name='x',type='tcp',host='127.0.0.1',port=a.port))
            self.assertFalse(ep1.connect(c,low))
            ep2=hive.Endpoint(dict(name='y',type='tcp',host='127.0.0.1',port=b.port))
            self.assertTrue(ep2.connect(c,high));ep2.drop()
        finally:a.close();b.close()
    def test_two_tcp_sessions_isolated(self):
        a,b=socket.socketpair(),socket.socketpair()
        h=hive.Hive(cfg())
        def read_line(sock):
            out=bytearray();sock.settimeout(2)
            while not out.endswith(b'\n'):
                out+=sock.recv(1)
            return out.decode().strip()
        threads=[]
        for pair in (a,b):
            thread=threading.Thread(target=h.tcp_client,args=(pair[0],('127.0.0.1',12345)),daemon=True)
            thread.start();threads.append(thread)
        try:
            for pair in (a,b):pair[1].sendall(b'isready\n')
            self.assertEqual(read_line(a[1]),'readyok')
            self.assertEqual(read_line(b[1]),'readyok')
            a[1].sendall(b'quit\n');a[1].close();threads[0].join(1)
            b[1].sendall(b'isready\n')
            self.assertEqual(read_line(b[1]),'readyok')
        finally:
            for pair in (a,b):
                for sock in pair:
                    try:sock.close()
                    except OSError:pass
            h.stopped.set()

    def test_simultaneous_uci_searches_do_not_share_replies(self):
        a,b=Server(slow=.08),Server(slow=.08)
        try:
            c=cfg(a,b);h=hive.Hive(c)
            for ep in h.registry.snapshot():h.registry._connect_and_test(ep)
            xout=[];yout=[]
            x=hive.Session(h,xout.append,'stdio');y=hive.Session(h,yout.append,'tcp')
            x.command('position startpos');y.command('position startpos moves d2d4')
            x.command('go depth 9 movetime 500 searchmoves e2e4 d2d4')
            y.command('go depth 9 movetime 500 searchmoves g1f3 c2c4')
            x.search_thread.join(3);y.search_thread.join(3)
            self.assertEqual(len([s for s in xout if s.startswith('bestmove ')]),1)
            self.assertEqual(len([s for s in yout if s.startswith('bestmove ')]),1)
            self.assertIn(xout[-1].split()[1],{'e2e4','d2d4'})
            self.assertIn(yout[-1].split()[1],{'g1f3','c2c4'})
            h.registry.stop()
        finally:a.close();b.close()

    def test_broadcast_payload(self):
        a=Server();c=cfg(a)
        try:
            r=hive.Registry(c,c['node_id']);r._connect_and_test(r.snapshot()[0])
            d=hive.Discovery(c,r,c['node_id']);p=json.loads(d.announce())
            self.assertEqual(p['nps'],500);self.assertEqual(p['port'],6250)
            r.stop()
        finally:a.close()

if __name__=='__main__':unittest.main(verbosity=2)
