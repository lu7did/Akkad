"""No tie remote UCI 'id name' to Nurse brain ID."""
import contextlib,io,json,socket,sys,tempfile,threading,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from nurse.config import read_brain
from nurse.uci import Nurse

class ArbitraryRemoteName(unittest.TestCase):
    def test_remote_name_different_from_brain(self):
        for identity in ('AlphaZero v99', 'Ajedrez de laboratorio 2', ''):
            with self.subTest(identity=identity),tempfile.TemporaryDirectory() as tmp:
                server=socket.socket();server.bind(('127.0.0.1',0));server.listen(1)
                port=server.getsockname()[1];messages=[]
                def serve():
                    try:
                        conn,_=server.accept()
                        with conn:
                            for line in conn.makefile('r',encoding='utf-8'):
                                msg=line.strip();messages.append(msg)
                                if msg=='uci':
                                    response=(('id name '+identity+'\n') if identity else '')+'uciok\n'
                                    conn.sendall(response.encode('utf-8'))
                                elif msg=='isready':conn.sendall(b'readyok\n')
                                elif msg=='quit':break
                    finally:server.close()
                th=threading.Thread(target=serve,daemon=True);th.start()
                path=Path(tmp)/'brains.json';path.write_text(json.dumps({'brains':{'picoSargon':{'type':'external','url':f'127.0.0.1:{port}','timeout':1000}}}),encoding='utf-8')
                with contextlib.redirect_stderr(io.StringIO()) as captured:
                    cfg=read_brain(path,'picoSargon')
                    self.assertNotIn('_expected_uci_name',cfg)
                    output=io.StringIO();n=Nurse(path,'picoSargon',output)
                    n.dispatch('uci');n.dispatch('isready');n._drop_transport()
                self.assertIn('uciok',output.getvalue())
                self.assertIn('readyok',output.getvalue())
                self.assertIn('UCI id name=',captured.getvalue())
                self.assertIn('uci',messages)
                th.join(timeout=2)
if __name__=='__main__':unittest.main()
