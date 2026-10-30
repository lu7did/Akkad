
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
uci-fics.py v0.1.0
Puente FICS <-> servidor UCI TCP.

Dependencia:
    python -m pip install python-chess
"""

import argparse
import getpass
import queue
import re
import socket
import sys
import threading
import time

try:
    import chess
except ImportError:
    sys.exit("Instalar dependencia: pip install python-chess")


VERSION = "0.1.0"


def log(icon, origin, message):
    stamp = time.strftime("%H:%M:%S")
    print(f"{stamp} {icon} [{origin}] {message}", flush=True)


class Connection:
    """Conexión TCP con lector independiente y soporte Telnet."""

    def __init__(self, name, host, port, events, telnet=False,
                 timeout=12):
        self.name = name
        self.events = events
        self.telnet = telnet
        self.sock = socket.create_connection(
            (host, port), timeout=timeout
        )
        self.sock.settimeout(None)
        self.lock = threading.Lock()
        self.running = True
        self.state = 0
        self.telnet_cmd = 0

        log("🔌", name, f"Conectado a {host}:{port}")

        self.thread = threading.Thread(
            target=self.reader, daemon=True
        )
        self.thread.start()

    def send(self, command, secret=False):
        with self.lock:
            self.sock.sendall(
                (command + "\n").encode("utf-8")
            )
        log("➡️", self.name,
            "***" if secret else command)

    def filter_telnet(self, data):
        # Telnet IAC=255, DO=253, DONT=254,
        # WILL=251, WONT=252, SB=250, SE=240.
        result = bytearray()

        for b in data:
            if self.state == 0:
                if b == 255:
                    self.state = 1
                else:
                    result.append(b)

            elif self.state == 1:
                if b == 255:
                    result.append(255)
                    self.state = 0
                elif b in (251, 252, 253, 254):
                    self.telnet_cmd = b
                    self.state = 2
                elif b == 250:
                    self.state = 3
                else:
                    self.state = 0

            elif self.state == 2:
                # Rechazar opciones Telnet desconocidas.
                if self.telnet_cmd == 253:
                    reply = bytes([255, 252, b])
                    self.sock.sendall(reply)
                elif self.telnet_cmd == 251:
                    reply = bytes([255, 254, b])
                    self.sock.sendall(reply)
                self.state = 0

            elif self.state == 3:
                if b == 255:
                    self.state = 4

            elif self.state == 4:
                self.state = 0 if b == 240 else 3

        return result.decode("latin-1", errors="replace")

    def reader(self):
        buffer = ""

        try:
            while self.running:
                data = self.sock.recv(8192)

                if not data:
                    break

                if self.telnet:
                    text = self.filter_telnet(data)
                else:
                    text = data.decode(
                        "utf-8", errors="replace"
                    )

                buffer += text.replace(
                    "\r\n", "\n"
                ).replace("\r", "\n")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    self.events.put((self.name, line))

                # Los prompts FICS pueden llegar sin LF.
                if self.telnet:
                    patterns = (
                        r"(?:login|username):\s*$",
                        r"password:\s*$",
                        r"fics%\s*$",
                        r"Press return to enter[^\n]*$",
                    )

                    if any(
                        re.search(p, buffer, re.I)
                        for p in patterns
                    ):
                        self.events.put(
                            (self.name, buffer.strip())
                        )
                        buffer = ""

            if buffer.strip():
                self.events.put(
                    (self.name, buffer.strip())
                )

        except OSError as exc:
            if self.running:
                self.events.put(
                    (self.name, f"__ERROR__ {exc}")
                )
        finally:
            if self.running:
                self.events.put(
                    (self.name, "__DISCONNECT__")
                )

    def close(self):
        self.running = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


def parse_style12(line):
    """
    Convierte el tablero FICS style 12 a FEN.

    Campos:
       0..7  tablero (8 filas)
       8     turno
       9     columna en passant
       10..13 derechos de enroque
       14    halfmove clock
       15    identificador partida
       16    blancas
       17    negras
       18    relación jugador/partida
       20    incremento
       23    reloj blancas
       24    reloj negras
       25    número de jugada
    """

    fields = line[5:].split()

    if len(fields) < 29:
        raise ValueError("style 12 incompleto")

    ranks = fields[:8]

    if any(
        len(rank) != 8 or
        re.search(r"[^prnbqkPRNBQK-]", rank)
        for rank in ranks
    ):
        raise ValueError("tablero inválido")

    fen_ranks = []

    for rank in ranks:
        compressed = re.sub(
            r"-+",
            lambda m: str(len(m.group())),
            rank
        )
        fen_ranks.append(compressed)

    turn = fields[8].lower()

    if turn not in ("w", "b"):
        raise ValueError("turno inválido")

    ep_file = int(fields[9])

    if ep_file < -1 or ep_file > 7:
        raise ValueError("en passant inválido")

    castling = "".join(
        c for c, flag in zip(
            "KQkq", fields[10:14]
        ) if flag == "1"
    ) or "-"

    if ep_file == -1:
        ep = "-"
    else:
        rank = "6" if turn == "w" else "3"
        ep = "abcdefgh"[ep_file] + rank

    halfmove = max(0, int(fields[14]))
    move_number = max(1, int(fields[25]))

    fen = (
        f"{'/'.join(fen_ranks)} "
        f"{turn} {castling} {ep} "
        f"{halfmove} {move_number}"
    )

    board = chess.Board(fen)

    if not board.is_valid():
        raise ValueError(f"FEN inválida: {fen}")

    return {
        "fen": fen,
        "board": board,
        "game": int(fields[15]),
        "white": fields[16],
        "black": fields[17],
        "relation": int(fields[18]),
        "increment": max(0, int(fields[20])) * 1000,
        "wtime": max(0, int(fields[23])) * 1000,
        "btime": max(0, int(fields[24])) * 1000,
        "last": fields[28],
    }


class FicsBridge:

    def __init__(self, args):
        self.args = args
        self.events = queue.Queue()

        self.uci = None
        self.fics = None

        self.username = None
        self.login_state = "waiting"
        self.fics_ready = False

        self.uci_name = "Desconocido"
        self.uci_ok = False
        self.uci_ready = False

        self.game_key = None
        self.current_position = None

        self.pending_fen = None
        self.pending_since = None
        self.stopping = False
        self.last_sent_fen = None

        self.challenge_name = None
        self.challenge_text = ""
        self.challenge_since = 0

    def initialize_fics(self):
        if self.fics_ready:
            return

        self.fics_ready = True

        log("👤", "FICS",
            f"Sesión iniciada como {self.username}")

        commands = [
            "iset nowrap 1",
            "set style 12",
            "set seek 0",
            "set shout 0",
            "set cshout 0",
            "set rated 0",
            "set open 1",
        ]

        for cmd in commands:
            self.fics.send(cmd)

        log("✅", "FICS",
            "Configuración inicial enviada")

    def reset_game(self):
        if self.pending_fen is not None:
            self.uci.send("stop")
            self.stopping = True

        self.pending_fen = None
        self.pending_since = None
        self.last_sent_fen = None
        self.current_position = None
        self.game_key = None

    def handle_login(self, line):
        if self.login_state == "waiting":
            if re.search(
                r"(?:login|username):\s*$",
                line, re.I
            ):
                self.fics.send(self.args.user)
                self.login_state = "username_sent"
            return

        if self.login_state == "username_sent":
            if re.search(r"password:\s*$", line, re.I):
                self.fics.send(
                    self.args.password, secret=True
                )
                self.login_state = "password_sent"
                return

            if (
                self.args.user.lower() == "guest"
                and re.search(
                    r"Press return to enter",
                    line, re.I
                )
            ):
                self.fics.send("")
                self.login_state = "guest_confirmed"
                return

        identity = re.search(
            r"Starting FICS session as\s+([\w-]+)",
            line, re.I
        )

        if identity:
            self.username = identity.group(1)
            self.login_state = "authenticated"
            self.initialize_fics()

        elif (
            not self.fics_ready
            and self.args.user.lower() != "guest"
            and self.login_state == "password_sent"
            and re.search(r"fics%\s*$", line, re.I)
        ):
            self.username = self.args.user
            self.login_state = "authenticated"
            self.initialize_fics()

    def handle_challenge(self, line):
        if not self.fics_ready or self.game_key:
            return

        match = re.search(
            r"\bChallenge:\s*([A-Za-z][\w-]*)",
            line, re.I
        )

        if match:
            name = match.group(1)

            self.challenge_name = name
            self.challenge_text = line
            self.challenge_since = time.monotonic()

        elif self.challenge_name:
            if time.monotonic() - self.challenge_since > 3:
                self.challenge_name = None
                return

            self.challenge_text += " " + line

        else:
            return

        description = self.challenge_text.lower()

        # No aceptar nada sin identificar explícitamente
        # que se trata de una partida unrated.
        if not re.search(r"\b(?:rated|unrated)\b",
                         description):
            return

        standard = bool(re.search(
            r"\b(blitz|lightning|standard|untimed)\b",
            description
        ))

        unusual = bool(re.search(
            r"\b(wild|bughouse|crazyhouse|"
            r"suicide|atomic|losers|chess960)\b",
            description
        ))

        if "unrated" in description and standard \
                and not unusual:
            log("🤝", "FICS",
                f"Aceptando desafío de "
                f"{self.challenge_name}")
            self.fics.send(
                f"accept {self.challenge_name}"
            )
        else:
            log("🚫", "FICS",
                "Desafío incompatible: rechazado")
            self.fics.send(
                f"decline {self.challenge_name}"
            )

        self.challenge_name = None
        self.challenge_text = ""

    def handle_position(self, line):
        try:
            pos = parse_style12(line)
        except ValueError as exc:
            log("⚠️", "FICS", str(exc))
            return

        # Relation 1 = jugamos blancas,
        # relation -1 = jugamos negras.
        if pos["relation"] not in (1, -1):
            return

        if not self.fics_ready or not self.username:
            return

        player_names = (
            pos["white"].lower(),
            pos["black"].lower()
        )

        if self.username.lower() not in player_names:
            return

        game_key = (
            pos["game"],
            pos["white"],
            pos["black"]
        )

        if game_key != self.game_key:
            self.reset_game()
            self.game_key = game_key

            color_name = (
                "blancas"
                if pos["relation"] == 1
                else "negras"
            )

            log("♟️", "PARTIDA",
                f"Juego #{pos['game']}: "
                f"{pos['white']} vs {pos['black']} "
                f"| {color_name}")

            if self.uci_ok:
                self.uci.send("ucinewgame")
                self.uci.send("isready")
                self.uci_ready = False

        self.current_position = pos

        my_color = (
            chess.WHITE if pos["relation"] == 1
            else chess.BLACK
        )

        if pos["board"].turn != my_color:
            return

        if pos["fen"] == self.last_sent_fen:
            return

        if self.pending_fen is not None:
            if pos["fen"] == self.pending_fen:
                return

            log("⚠️", "SYNC",
                "Posición modificada durante búsqueda")
            self.uci.send("stop")
            self.stopping = True
            self.pending_fen = None
            self.pending_since = None
            return

        self.maybe_search()

    def maybe_search(self):
        pos = self.current_position

        if (
            pos is None
            or self.game_key is None
            or not self.uci_ok
            or not self.uci_ready
            or self.stopping
            or self.pending_fen is not None
        ):
            return

        my_color = (
            chess.WHITE if pos["relation"] == 1
            else chess.BLACK
        )

        if pos["board"].turn != my_color:
            return

        if pos["fen"] == self.last_sent_fen:
            return

        self.pending_fen = pos["fen"]
        self.pending_since = time.monotonic()

        self.uci.send(
            f"position fen {pos['fen']}"
        )

        if self.args.movetime:
            self.uci.send(
                f"go movetime {self.args.movetime}"
            )
        else:
            self.uci.send(
                f"go wtime {pos['wtime']} "
                f"btime {pos['btime']} "
                f"winc {pos['increment']} "
                f"binc {pos['increment']}"
            )

        log("🧠", "UCI",
            f"Buscando jugada para {pos['fen']}")

    def handle_uci(self, line):
        if line:
            log("🤖", "UCI", line)

        if line.startswith("id name "):
            self.uci_name = line[8:]

        elif line.strip() == "uciok":
            self.uci_ok = True
            self.uci.send("isready")

        elif line.strip() == "readyok":
            self.uci_ready = True
            log("✅", "UCI",
                f"Motor disponible: {self.uci_name}")
            self.maybe_search()

        elif line.startswith("bestmove "):
            result = re.match(
                r"bestmove\s+(\S+)", line
            )

            if not result:
                return

            if self.stopping:
                self.stopping = False
                self.uci.send("isready")
                self.uci_ready = False
                return

            if self.pending_fen is None:
                return

            move = result.group(1).lower()
            original_fen = self.pending_fen

            self.pending_fen = None
            self.pending_since = None

            if move in ("(none)", "0000"):
                log("⚠️", "UCI",
                    "El motor no proporcionó jugada")
                return

            board = chess.Board(original_fen)

            try:
                chess_move = chess.Move.from_uci(move)
            except ValueError:
                log("❌", "UCI",
                    f"Formato inválido: {move}")
                return

            if chess_move not in board.legal_moves:
                log("❌", "UCI",
                    f"Jugada ilegal: {move}")
                return

            # FICS acepta jugadas coordenadas,
            # incluidas promociones con sufijo.
            self.last_sent_fen = original_fen
            self.fics.send(move)

            log("♟️", "PARTIDA",
                f"Jugada enviada: {move}")

    def handle_fics(self, line):
        if line:
            log("🌐", "FICS", line)

        if re.search(
            r"registered name|already logged in|"
            r"invalid login|invalid password",
            line, re.I
        ) and not self.fics_ready:
            raise RuntimeError(
                f"FICS rechazó el login: {line}"
            )

        if not self.fics_ready:
            self.handle_login(line)

        if line.startswith("<12> "):
            self.handle_position(line)
            return

        self.handle_challenge(line)

        if re.search(
            r"\{Game\s+\d+.*\}\s+"
            r"(?:1-0|0-1|1/2-1/2|\*)",
            line
        ):
            log("🏁", "FICS", "Fin de partida")
            self.reset_game()

    def run(self):
        a = self.args

        log("🚀", "APP",
            f"uci-fics v{VERSION} | "
            f"Python {sys.version.split()[0]}")

        try:
            self.uci = Connection(
                "UCI", a.ip, a.port,
                self.events,
                timeout=a.connect_timeout
            )

            self.uci.send("uci")

            self.fics = Connection(
                "FICS", a.ip_fics, a.port_fics,
                self.events,
                telnet=True,
                timeout=a.connect_timeout
            )

            log("🛡️", "APP",
                "Aceptación automática: unrated "
                "estándar exclusivamente")

            while True:
                try:
                    source, line = self.events.get(
                        timeout=0.25
                    )
                except queue.Empty:
                    source = None

                if source is not None:
                    if line == "__DISCONNECT__":
                        raise ConnectionError(
                            f"Conexión {source} cerrada"
                        )

                    if line.startswith("__ERROR__"):
                        raise ConnectionError(
                            f"{source}: {line}"
                        )

                    if source == "UCI":
                        self.handle_uci(line)

                    elif source == "FICS":
                        self.handle_fics(line)

                self.maybe_search()

                if (
                    self.pending_since is not None
                    and not self.stopping
                    and time.monotonic()
                    - self.pending_since
                    > a.engine_timeout
                ):
                    log("⏱️", "UCI",
                        "Timeout de búsqueda: stop")
                    self.uci.send("stop")
                    self.stopping = True
                    self.pending_since = None

        finally:
            for conn in (self.uci, self.fics):
                if conn:
                    try:
                        conn.send("quit")
                    except OSError:
                        pass
                    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Puente entre servidor UCI TCP "
            "y Free Internet Chess Server"
        )
    )

    parser.add_argument(
        "--ip", default="127.0.0.1"
    )
    parser.add_argument(
        "--port", type=int, default=6110
    )
    parser.add_argument(
        "--ip_fics", default="freechess.org"
    )
    parser.add_argument(
        "--port_fics", type=int, default=5000
    )
    parser.add_argument(
        "--user", default="guest"
    )
    parser.add_argument(
        "--password", default=None
    )
    parser.add_argument(
        "--movetime", type=int, default=0,
        help="Tiempo por jugada en ms; 0 = relojes FICS"
    )
    parser.add_argument(
        "--engine-timeout", type=float, default=90
    )
    parser.add_argument(
        "--connect-timeout", type=float, default=12
    )

    args = parser.parse_args()

    if args.password is None:
        if args.user.lower() == "guest":
            args.password = ""
        else:
            args.password = getpass.getpass(
                "Contraseña FICS: "
            )

    if args.movetime < 0:
        parser.error("--movetime debe ser >= 0")

    if args.engine_timeout <= 0:
        parser.error(
            "--engine-timeout debe ser positivo"
        )

    try:
        FicsBridge(args).run()
    except KeyboardInterrupt:
        log("🛑", "APP", "Detenido por el usuario")
    except (OSError, RuntimeError) as exc:
        log("❌", "APP", str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()

