"""Multi-client TCP UCI proxy; every session owns one Nurse instance."""
import argparse,socket,threading,sys,signal
from .uci import Nurse
from .telemetry import log

def serve_client(sock,addr,brains,ident):
    log(f'✅ TCP client connected from {addr}')
    nurse=None
    try:
        with sock.makefile('r',encoding='utf-8',errors='replace',newline='\n') as inp, sock.makefile('w',encoding='utf-8',newline='\n') as out:
            nurse=Nurse(brains,ident,out)
            nurse.run(inp)
    except (OSError,ValueError,ConnectionError) as e:log(f'❌ sesión {addr}: {e}')
    finally:
        try:sock.close()
        except OSError:pass
        log(f'🔌 TCP client disconnected {addr}')

def main(argv=None):
    ap=argparse.ArgumentParser(description='Nurse TCP/UCI server')
    ap.add_argument('--brains',required=True);ap.add_argument('--id',required=True)
    ap.add_argument('--ip',default='0.0.0.0');ap.add_argument('--port',type=int,default=6200)
    a=ap.parse_args(argv)
    # Validate profile before binding, no misleading listener on config failure.
    from .config import read_brain
    read_brain(a.brains,a.id)
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        srv.bind((a.ip,a.port));srv.listen();srv.settimeout(.5)
        log(f'🌐 Nurse TCP listener {a.ip}:{a.port} brain={a.id}')
        try:
            while True:
                try:client,addr=srv.accept()
                except socket.timeout:continue
                threading.Thread(target=serve_client,args=(client,addr,a.brains,a.id),daemon=True).start()
        except KeyboardInterrupt:log('🛑 Interrupción del usuario (Ctrl+C): listener Nurse detenido')
    return 0
if __name__=='__main__':raise SystemExit(main())
