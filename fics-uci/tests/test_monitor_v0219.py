"""Monitor fanout tests; python -m pytest fics-uci/tests/test_monitor_v0219.py."""
import importlib.util
import socket
import time
from pathlib import Path


def test_monitor_fanout():
    path = Path(__file__).resolve().parents[1] / "src" / "fics_uci.py"
    spec = importlib.util.spec_from_file_location("fics_uci_monitor_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monitor = module.UCIMonitor(0, "127.0.0.1")
    assert monitor.start()
    try:
        port = monitor.sock.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2) as first, \
             socket.create_connection(("127.0.0.1", port), timeout=2) as second:
            first.settimeout(2)
            second.settimeout(2)
            deadline = time.monotonic() + 2
            while len(monitor.clients) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            assert len(monitor.clients) == 2
            monitor.publish("position startpos moves e2e4")
            for client in (first, second):
                assert b"position startpos moves e2e4\n" in client.recv(256)
            first.close()
            monitor.publish("bestmove e7e5")
            assert b"bestmove e7e5" in second.recv(256)
    finally:
        monitor.close()
