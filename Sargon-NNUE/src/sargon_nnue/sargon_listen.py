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
#* sargon_listen.py
#* Atiende conexiones TCP y crea sesiones del motor UCI
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations

import argparse
import socket
import sys
import threading
import signal

from . import __version__
from .cli_common import add_engine_args
from .factory import build_engine
from .uci import UCISession
from .brains import inject


def log(s: str) -> None:
    print(s, file=sys.stderr, flush=True)


def parser():
    p = argparse.ArgumentParser(description="Sargon-NNUE UCI listener TCP/STDIN")
    p.add_argument("--mode", choices=["TCP", "STDIN"], default="TCP")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=6200)
    p.add_argument("--once", action="store_true", help="TCP: termina tras una sesión")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    add_engine_args(p)
    p.add_argument("--brain",help="archivo data/brains/brains.json")
    p.add_argument("--id",help="ID del brain en JSON")
    return p


def _close_socket(conn: socket.socket) -> None:
    try:
        conn.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        conn.close()
    except OSError:
        pass


class _SessionRegistry:
    """Registro de sesiones TCP independientes actualmente activas.

    No existe una sesión propietaria ni una conexión preferida: todas las
    conexiones aceptadas pueden coexistir. El registro sólo se usa para
    telemetría y para cerrar limpiamente todos los sockets al apagar el
    listener; nunca serializa búsquedas ni reemplaza sesiones.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[int, tuple[socket.socket, tuple[str, int]]] = {}
        self._next_id = 1

    def add(self, conn: socket.socket, addr: tuple[str, int]) -> tuple[int, int]:
        with self._lock:
            session_id = self._next_id
            self._next_id += 1
            self._sessions[session_id] = (conn, addr)
            return session_id, len(self._sessions)

    def remove(self, session_id: int) -> int:
        with self._lock:
            self._sessions.pop(session_id, None)
            return len(self._sessions)

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def close_all(self) -> None:
        with self._lock:
            conns = [conn for conn, _ in self._sessions.values()]
            self._sessions.clear()
        for conn in conns:
            _close_socket(conn)


def _configure_connection(conn: socket.socket) -> None:
    try:
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except OSError:
        pass


def _run_tcp_session(
    conn: socket.socket,
    addr: tuple[str, int],
    session_id: int,
    args,
    registry: _SessionRegistry,
) -> None:
    evaluator = None
    player = None
    try:
        evaluator, player = build_engine(args)
        log(
            f"🧩 Sargon-NNUE v{__version__} sesión #{session_id} {addr[0]}:{addr[1]} "
            f"🧠 evaluator={evaluator.name} 🎮 player={player.name}"
        )

        with conn:
            with conn.makefile("r", encoding="utf-8", errors="replace", newline="\n") as r:
                with conn.makefile("w", encoding="utf-8", newline="\n") as w:
                    # Cada conexión posee Board + Player + Evaluator propios.
                    # No hay lock global de choose(): las partidas son concurrentes.
                    UCISession(player, r, w, log, brain_name=args.brain_name).loop()
    except (ConnectionError, OSError, ValueError) as exc:
        log(f"⚠️ sesión #{session_id} {addr[0]}:{addr[1]} terminada: {exc}")
    except Exception as exc:
        log(
            f"❌ sesión #{session_id} {addr[0]}:{addr[1]}: "
            f"{type(exc).__name__}: {exc}"
        )
    finally:
        audit = getattr(player, "audit", None) if player is not None else None
        if audit is not None:
            try:
                audit.summary()
            except Exception as exc:
                log(f"⚠️ sesión #{session_id}: error cerrando auditoría: {exc}")
        if player is not None:
            try:
                player.close()
            except Exception as exc:
                log(f"⚠️ sesión #{session_id}: error cerrando player: {exc}")
        if evaluator is not None:
            try:
                evaluator.close()
            except Exception as exc:
                log(f"⚠️ sesión #{session_id}: error cerrando evaluator: {exc}")
        active = registry.remove(session_id)
        log(f"🔌 sesión #{session_id} cerrada; activas={active}")


def _run_stdin(args) -> int:
    evaluator, player = build_engine(args)
    log(f"🧩 Sargon-NNUE v{__version__} 🧠 evaluator={evaluator.name} 🎮 player={player.name}")
    try:
        UCISession(player, sys.stdin, sys.stdout, log, brain_name=args.brain_name).loop()
        return 0
    finally:
        audit = getattr(player, "audit", None)
        if audit is not None:
            audit.summary()
        player.close()
        evaluator.close()


def main(argv=None):
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    # brains.inject() replaces --brain/--id with engine parameters;
    # retain the selected profile ID for the UCI identity of each session.
    brain_name = "default"
    for index, token in enumerate(raw_argv):
        if token == "--id" and index + 1 < len(raw_argv):
            brain_name = raw_argv[index + 1]
    try:
        args = parser().parse_args(inject(raw_argv))
        args.brain_name = brain_name
    except ValueError as exc:
        parser().error(str(exc))

    if args.mode == "STDIN":
        return _run_stdin(args)

    registry = _SessionRegistry()
    threads: list[threading.Thread] = []
    stop_event = threading.Event()
    server_ref: dict[str, socket.socket | None] = {"socket": None}

    def request_stop(signum=None, frame=None) -> None:
        # El handler debe ser mínimo y seguro. No hace trabajo pesado:
        # marca la parada y cierra el socket de escucha para despertar accept().
        if not stop_event.is_set():
            stop_event.set()
            log("🛑 señal de terminación recibida; cerrando listener...")
        srv = server_ref.get("socket")
        if srv is not None:
            try:
                srv.close()
            except OSError:
                pass

    old_sigint = signal.getsignal(signal.SIGINT)
    old_sigterm = signal.getsignal(signal.SIGTERM) if hasattr(signal, "SIGTERM") else None
    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    exit_code = 0
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_ref["socket"] = srv
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((args.host, args.port))
        srv.listen()
        # Evita depender de que Windows interrumpa un accept() bloqueante con Ctrl+C.
        srv.settimeout(0.5)
        log(f"🌐 TCP UCI escuchando en {args.host}:{args.port} (multi-sesión)")

        while not stop_event.is_set():
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                if stop_event.is_set():
                    break
                raise

            _configure_connection(conn)
            session_id, active = registry.add(conn, addr)
            log(
                f"🔌 conexión #{session_id} {addr[0]}:{addr[1]} "
                f"aceptada; activas={active}"
            )

            if args.once:
                _run_tcp_session(conn, addr, session_id, args, registry)
                break

            t = threading.Thread(
                target=_run_tcp_session,
                args=(conn, addr, session_id, args, registry),
                daemon=True,
                name=f"uci-{session_id}-{addr[0]}:{addr[1]}",
            )
            threads.append(t)
            t.start()
            threads = [thr for thr in threads if thr.is_alive()]

    except KeyboardInterrupt:
        # Respaldo por si una plataforma entrega KeyboardInterrupt en vez de
        # invocar el handler instalado.
        stop_event.set()
        exit_code = 130
        log("🛑 listener interrumpido")
    finally:
        stop_event.set()
        registry.close_all()
        srv = server_ref.get("socket")
        if srv is not None:
            try:
                srv.close()
            except OSError:
                pass
        server_ref["socket"] = None

        # Los threads son daemon, pero damos una oportunidad breve a que salgan
        # después de cerrar sus sockets. Nunca bloqueamos indefinidamente el cierre.
        for t in threads:
            t.join(timeout=0.5)

        signal.signal(signal.SIGINT, old_sigint)
        if hasattr(signal, "SIGTERM") and old_sigterm is not None:
            signal.signal(signal.SIGTERM, old_sigterm)

        log("✅ listener detenido")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
