#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* test_session_owner.py
#* Ejecuta pruebas de regresion para test session owner
#* v0.6.153
#=================================================================================================================*
import socket

from sargon_nnue.sargon_listen import _SessionRegistry


def test_registry_keeps_multiple_connections_alive():
    registry = _SessionRegistry()
    a1, b1 = socket.socketpair()
    a2, b2 = socket.socketpair()
    try:
        id1, count1 = registry.add(a1, ("127.0.0.1", 1001))
        id2, count2 = registry.add(a2, ("127.0.0.1", 1002))

        assert id1 != id2
        assert count1 == 1
        assert count2 == 2
        assert registry.count() == 2

        # Agregar la segunda conexión NO debe cerrar la primera.
        b1.settimeout(0.2)
        a1.sendall(b"x")
        assert b1.recv(1) == b"x"

        assert registry.remove(id1) == 1
        assert registry.count() == 1
        assert registry.remove(id2) == 0
    finally:
        registry.close_all()
        for s in (a1, b1, a2, b2):
            try:
                s.close()
            except OSError:
                pass


def test_close_all_closes_every_registered_socket():
    registry = _SessionRegistry()
    a1, b1 = socket.socketpair()
    a2, b2 = socket.socketpair()
    try:
        registry.add(a1, ("127.0.0.1", 1001))
        registry.add(a2, ("127.0.0.1", 1002))
        registry.close_all()

        for peer in (b1, b2):
            peer.settimeout(0.2)
            assert peer.recv(1) == b""
        assert registry.count() == 0
    finally:
        for s in (a1, b1, a2, b2):
            try:
                s.close()
            except OSError:
                pass
