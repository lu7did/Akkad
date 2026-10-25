
$ErrorActionPreference = "Stop"

$Python = "C:\Users\pedro\ufasta\Scripts\python.exe"
$Script = Join-Path $env:TEMP "picosargon_tcp_test.py"

@'
import socket

HOST = "picosargon.local"
PORT = 6110

print(f"Conectando a {HOST}:{PORT}...", flush=True)

with socket.create_connection((HOST, PORT), timeout=5) as s:
    print("TCP conectado", flush=True)

    s.settimeout(5)
    s.sendall(b"uci\nisready\n")

    data = b""

    try:
        #while b"readyok" not in data:
        while b"bestmove" not in data:
            chunk = s.recv(4096)
            if not chunk:
                print("Servidor cerro la conexion")
                break
            data += chunk

    except socket.timeout:
        print("Timeout esperando respuesta UCI")

    print("--- Respuesta UCI ---")
    print(data.decode("utf-8", errors="replace"))

    s.sendall(b"quit\n")

print("Prueba finalizada")
'@ | Set-Content -LiteralPath $Script -Encoding UTF8

& $Python $Script

if ($LASTEXITCODE -ne 0) {
    throw "Error ejecutando prueba TCP/UCI"
}

