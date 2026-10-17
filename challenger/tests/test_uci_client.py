import socket
import threading
from challenger.uci_client import TCPUCIClient

def test_handshake_and_result_option():
    listener=socket.socket(); listener.bind(('127.0.0.1',0)); listener.listen(1)
    port=listener.getsockname()[1]; seen=[]
    def server():
        conn,_=listener.accept(); f=conn.makefile('r',encoding='utf-8')
        for raw in f:
            line=raw.strip(); seen.append(line)
            if line=='uci': conn.sendall(b'id name Fake\noption name NyxResult type string default none\nuciok\n')
            elif line=='isready': conn.sendall(b'readyok\n')
            elif line=='quit': break
        conn.close(); listener.close()
    t=threading.Thread(target=server); t.start()
    c=TCPUCIClient('127.0.0.1',port,timeout_ms=2000); c.connect()
    assert c.id_name=='Fake'; assert 'NyxResult' in c.options
    c.report_result_if_supported('1-0','CHECKMATE'); c.close(); t.join(2)
    assert any(x.startswith('setoption name NyxResult value 1-0') for x in seen)
