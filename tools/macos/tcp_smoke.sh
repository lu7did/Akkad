#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$HERE/../.." && pwd -P)"
HOST="${LISTEN_HOST:-127.0.0.1}"
PORT="${LISTEN_PORT:-6200}"
python3 - "$HOST" "$PORT" <<'PYTEST'
import socket,sys
host,port=sys.argv[1],int(sys.argv[2])
with socket.create_connection((host,port),timeout=5) as s:
    s.settimeout(30)
    s.sendall(b"uci\nisready\nposition startpos\ngo depth 2 movetime 1000\n")
    data=b""
    while b"bestmove " not in data:
        part=s.recv(4096)
        if not part:break
        data+=part
    s.sendall(b"quit\n")
    print(data.decode('utf-8','replace'))
    assert b"uciok" in data and b"readyok" in data and b"bestmove " in data
    print("PASS: UCI TCP smoke test")
PYTEST
