#!/usr/bin/env python3
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
#* sargon_bridge.py
#* Transparently bridges a standard UCI subprocess interface to Sargon TCP UCI.
#=================================================================================================================*
"""UCI stdio <-> Sargon TCP bridge, using only the Python standard library.

All stdout bytes originate from the TCP server. Diagnostics go to stderr.
TCP disconnects during a session are fatal: reconnecting would silently lose
board/game state, so the parent process must start a new bridge/session.
"""

import argparse
import socket
import sys
import threading
import time

DEFAULT_HOST = "192.168.68.108"
DEFAULT_PORT = 6110  #  picoSargon (Raspberry Pico lwl)

def diagnostic(message):
    print("[sargon_bridge] " + message, file=sys.stderr, flush=True)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="UCI stdin/stdout <-> Sargon TCP bridge")
    parser.add_argument("--ip", default=DEFAULT_HOST, help="Sargon listen IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Sargon TCP port (default: 6200)")
    parser.add_argument("--connect-timeout", type=float, default=5.0, help="TCP connect timeout, seconds")
    parser.add_argument("--attempts", type=int, default=3, help="Initial connection attempts (default: 3)")
    parser.add_argument("--retry-delay", type=float, default=1.0, help="Seconds between connection attempts")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.connect_timeout <= 0 or args.attempts < 1 or args.retry_delay < 0:
        parser.error("invalid connection retry parameters")
    return args


def connect(args):
    for attempt in range(1, args.attempts + 1):
        try:
            sock = socket.create_connection((args.ip, args.port), timeout=args.connect_timeout)
            sock.settimeout(None)  # Searches can legitimately run for a long time.
            diagnostic("TCP connected to {}:{}".format(args.ip, args.port))
            return sock
        except OSError as exc:
            diagnostic("TCP connection attempt {}/{} failed: {}".format(attempt, args.attempts, exc))
            if attempt < args.attempts:
                time.sleep(args.retry_delay)
    return None


def run(args):
    sock = connect(args)
    if sock is None:
        return 2

    stop = threading.Event()
    quit_sent = threading.Event()
    stdin_eof = threading.Event()
    send_failed = threading.Event()

    def stdin_to_tcp():
        try:
            while not stop.is_set():
                line = sys.stdin.buffer.readline()
                if not line:
                    stdin_eof.set()
                    # stdin was closed by lichess-bot. Request a clean UCI exit.
                    if not quit_sent.is_set():
                        try:
                            sock.sendall(b"quit\n")
                            quit_sent.set()
                        except OSError:
                            pass
                    break
                try:
                    sock.sendall(line)
                except OSError as exc:
                    send_failed.set()
                    diagnostic("TCP send failed: {}".format(exc))
                    break
                if line.strip().lower() == b"quit":
                    quit_sent.set()
                    break
        except (OSError, ValueError) as exc:
            send_failed.set()
            diagnostic("stdin read failed: {}".format(exc))
        finally:
            # Signal that no further bytes will be sent; leave read-side open
            # to receive any pending responses until peer closes.
            try:
                sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    sender = threading.Thread(target=stdin_to_tcp, name="uci-stdin", daemon=True)
    sender.start()
    result = 0
    try:
        while True:
            data = sock.recv(65536)
            if not data:
                if not (quit_sent.is_set() or stdin_eof.is_set()):
                    diagnostic("Sargon server disconnected unexpectedly; UCI state is lost")
                    result = 3
                break
            # stdout strictly carries the server's UCI bytes, nothing else.
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
    except (OSError, BrokenPipeError) as exc:
        diagnostic("connection or stdout failed: {}".format(exc))
        result = 3
    finally:
        stop.set()
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()
        # The daemon thread may still be waiting on stdin; that cannot block exit.
        sender.join(timeout=0.1)
        diagnostic("TCP disconnected")
    if send_failed.is_set() and not quit_sent.is_set():
        result = 3
    return result


def main(argv=None):
    args = parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        diagnostic("interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
