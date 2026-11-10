"""Console-provenance regression: show one endpoint line and preserve move layout."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class BenchProvenance(unittest.TestCase):
    def test_one_external_endpoint_line_outside_move_loop(self):
        src=(ROOT/'src/nurse/benchmark.py').read_text(encoding='utf-8')
        self.assertIn("if backend_type=='external':",src)
        self.assertIn("details=engine.external_provenance",src)
        self.assertIn("TCP {host} DNS=[{resolved}] conectado={peer} origen={local} id_name={remote}",src)
        self.assertLess(src.index("if backend_type=='external':",src.index('def benchmark_one(')),src.index('if args.warmup:',src.index('def benchmark_one(')))
        self.assertIn("nodes={str(row['nodes'])",src)
    def test_dns_and_live_peer_logged(self):
        src=(ROOT/'src/nurse/transport.py').read_text(encoding='utf-8')
        self.assertIn('socket.getaddrinfo(',src)
        self.assertIn('self.sock.getpeername()',src)
        self.assertIn('self.sock.getsockname()',src)
        self.assertIn("'peer_ip':peer[0]",src)
if __name__=='__main__':unittest.main()
