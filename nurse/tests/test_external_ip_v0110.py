"""v0.1.10: show resolved and real peer IP, never validate remote UCI name."""
import contextlib,io,json,socket,sys,tempfile,threading,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from nurse.uci import Nurse
from nurse.transport import Transport,TransportError

class RemoteIPTest(unittest.TestCase):
    def server(self):
        sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        sock.bind(('127.0.0.1',0));sock.listen(1)
        port=sock.getsockname()[1]
        received=[]
        def target():
            try:
                c,_=sock.accept()
                with c:
                    for raw in c.makefile('r',encoding='utf-8'):
                        line=raw.strip();received.append(line)
                        if line=='uci': c.sendall(b'id name Motor con nombre arbitrario\nuciok\n')
                        elif line=='isready':c.sendall(b'readyok\n')
                        elif line.startswith('go '):c.sendall(b'info depth 2 nodes 17 time 1\nbestmove e2e4\n')
                        elif line=='quit':break
            finally:sock.close()
        thread=threading.Thread(target=target,daemon=True);thread.start()
        return port,received,thread
    def test_socket_dns_peer_and_provenance_not_name_validation(self):
        port,received,thread=self.server()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'brains.json'
            path.write_text(json.dumps({'brains':{'picoSargon':{'type':'external','url':f'localhost:{port}','tmax':1000,'timeout':2000}}}),encoding='utf-8')
            out=io.StringIO()
            with contextlib.redirect_stderr(io.StringIO()) as logs:
                n=Nurse(path,'picoSargon',out)
                self.assertTrue(n.dispatch('uci'))
                self.assertTrue(n.dispatch('isready'))
                self.assertEqual(n.transport.peer_address[0],'127.0.0.1')
                provenance=n.transport.provenance()
                self.assertEqual(provenance['peer_ip'],'127.0.0.1')
                self.assertEqual(provenance['requested'],f'localhost:{port}')
                self.assertEqual(provenance['uci_name'],'Motor con nombre arbitrario')
                n._drop_transport()
            output=out.getvalue()
            lines=[x for x in output.splitlines() if x.startswith('info string nurse_external_provenance ')]
            self.assertEqual(len(lines),1)
            item=json.loads(lines[0][len('info string nurse_external_provenance '):])
            self.assertEqual(item['peer_ip'],'127.0.0.1')
            self.assertIn('127.0.0.1',item['dns'])
            self.assertEqual(item['uci_name'],'Motor con nombre arbitrario')
            self.assertIn('TCP DNS host=',logs.getvalue())
            self.assertIn('TCP socket fd=',logs.getvalue())
            self.assertIn('uciok',output)
            self.assertIn('readyok',output)
        thread.join(2)
        self.assertIn('uci',received)
    def test_unresolvable_fails_without_fallback(self):
        t=Transport()
        with self.assertRaises(TransportError):
            t.tcp('nonexistent.invalid',6110,timeout=.1)
        self.assertIsNone(t.sock)

if __name__=='__main__':unittest.main()
