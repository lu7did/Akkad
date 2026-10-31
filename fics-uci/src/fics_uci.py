#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fics_uci.py v0.2.17 — puente FICS/Telnet ↔ UCI/TCP con historial verificado.

Requiere: pip install python-chess
No utiliza motores externos por subprocess: --ip/--port apuntan a un servidor UCI TCP.
"""
import argparse
import getpass
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import yaml
import queue
import re
import socket
import sys
import threading
import time

try:
    import chess
except ImportError:
    sys.exit("Instalá python-chess: python -m pip install python-chess")

VERSION = "0.2.17"

VERBOSE = False

# Un unico criterio de origen para toda la telemetria. El primer argumento
# se conserva por compatibilidad con las llamadas existentes, pero no determina
# el icono: este se asigna exclusivamente por el origen del mensaje.
BRIDGE_SOURCES = frozenset({"APP", "SYNC", "PARTIDA", "SEEK", "JSON", "BRIDGE"})

def log(emoji, source, message, detail=False):
    if detail and not VERBOSE:
        return
    origin = str(source).upper()
    if origin == "FICS":
        emoji = "➡️"
    elif origin == "UCI":
        emoji = "🧠"
    elif origin in BRIDGE_SOURCES:
        emoji = "✅"
    else:
        emoji = "📊"
    print(f"{time.strftime('%H:%M:%S')} {emoji} [{source}] {message}", flush=True)


def format_clock(milliseconds):
    seconds = max(0, int(milliseconds)) // 1000
    return f"{seconds // 3600:d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}" if seconds >= 3600 else f"{seconds // 60:02d}:{seconds % 60:02d}"


def classify_game(minutes, increment):
    # Clasificación convencional FICS, si no se conoce la anunciada.
    effective = minutes * 60 + increment * 40
    return "lightning" if effective < 180 else "blitz" if effective < 900 else "standard"


def normalize_brain_name(name):
    """Use the brain ID from Sargon-NNUE UCI; keep external UCI names unchanged."""
    name = str(name or "").strip()
    match = re.fullmatch(r"sargon[_-]nnue\(([^)]+)\)(?:\s+v[^\s]+)?", name, flags=re.IGNORECASE)
    return match.group(1).strip() if match else (name or "Desconocido")


class SocketLink:
    def __init__(self, name, host, port, events, telnet=False):
        self.name, self.events, self.telnet = name, events, telnet
        self.sock = socket.create_connection((host, port), timeout=15)
        self.sock.settimeout(None)
        self.lock = threading.Lock()
        self.running = True
        self.telnet_state = 0
        self.telnet_command = 0
        self.buffer = ""
        self.thread = threading.Thread(target=self.read, daemon=True)
        self.thread.start()
        log("🔌", name, f"Conectado a {host}:{port}")

    def send(self, text, secret=False):
        with self.lock:
            self.sock.sendall((text + "\n").encode("utf-8"))
        if not secret:
            detailed = (text.startswith(("position ", "go ")) or
                        (self.name == "FICS" and bool(re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", text))))
            log("➡️", self.name, text, detail=detailed)
        else:
            log("➡️", self.name, "***")

    def decode_telnet(self, data):
        output = bytearray()
        for byte in data:
            if self.telnet_state == 0:
                if byte == 255:
                    self.telnet_state = 1
                else:
                    output.append(byte)
            elif self.telnet_state == 1:
                if byte == 255:
                    output.append(255)
                    self.telnet_state = 0
                elif byte in (251, 252, 253, 254):
                    self.telnet_command = byte
                    self.telnet_state = 2
                elif byte == 250:
                    self.telnet_state = 3
                else:
                    self.telnet_state = 0
            elif self.telnet_state == 2:
                with self.lock:
                    if self.telnet_command == 251:
                        self.sock.sendall(bytes([255, 254, byte]))
                    elif self.telnet_command == 253:
                        self.sock.sendall(bytes([255, 252, byte]))
                self.telnet_state = 0
            elif self.telnet_state == 3:
                if byte == 255:
                    self.telnet_state = 4
            elif self.telnet_state == 4:
                self.telnet_state = 0 if byte == 240 else 3
        return output.decode("latin-1", errors="replace")

    def read(self):
        try:
            while self.running:
                data = self.sock.recv(8192)
                if not data:
                    break
                text = self.decode_telnet(data) if self.telnet else data.decode("utf-8", "replace")
                # FICS envía BEL (ASCII 0x07) para avisos. No reproducirlo.
                # Conservamos el resto del texto y su telemetría.
                text = text.replace("\x07", "")
                self.buffer += text.replace("\r\n", "\n").replace("\r", "\n")
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    self.events.put((self.name, self, line))
                if self.telnet and re.search(
                    r"(?:login:|password:|fics%|Press return to enter[^\n]*)\s*$",
                    self.buffer, re.I,
                ):
                    self.events.put((self.name, self, self.buffer.strip()))
                    self.buffer = ""
        except OSError as exc:
            if self.running:
                self.events.put((self.name, self, f"__ERROR__ {exc}"))
        finally:
            if self.running:
                self.events.put((self.name, self, "__DISCONNECT__"))

    def close(self):
        self.running = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


def style12(line):
    fields = line[5:].split()
    if len(fields) < 29:
        raise ValueError("style12 incompleto")
    ranks = fields[:8]
    if any(len(r) != 8 or re.search(r"[^prnbqkPRNBQK-]", r) for r in ranks):
        raise ValueError("tablero inválido")
    rows = [re.sub(r"-+", lambda match: str(len(match.group())), r) for r in ranks]
    turn = fields[8].lower()
    epfile = int(fields[9])
    if turn not in ("w", "b") or not -1 <= epfile <= 7:
        raise ValueError("turno/en passant inválido")
    castles = "".join(c for c, flag in zip("KQkq", fields[10:14]) if flag == "1") or "-"
    ep = "-" if epfile == -1 else "abcdefgh"[epfile] + ("6" if turn == "w" else "3")
    fen = f"{'/'.join(rows)} {turn} {castles} {ep} {max(0,int(fields[14]))} {max(1,int(fields[25]))}"
    board = chess.Board(fen)
    if not board.is_valid():
        raise ValueError(f"posición inválida: {fen}")
    return {
        "board": board, "fen": fen, "game": int(fields[15]),
        "white": fields[16], "black": fields[17], "relation": int(fields[18]),
        # style 12: reloj restante en milisegundos, incremento en segundos.
        "wtime": max(0, int(fields[23])) * 1000, "btime": max(0, int(fields[24])) * 1000,
        "increment": max(0, int(fields[20])) * 1000,
        "initial_minutes": max(0, int(fields[19])),
    }


def same_position(a, b):
    return (a.board_fen() == b.board_fen()
            and a.turn == b.turn
            and a.castling_rights == b.castling_rights
            and a.ep_square == b.ep_square
            and a.fullmove_number == b.fullmove_number
            and a.halfmove_clock == b.halfmove_clock)


class History:
    def __init__(self):
        self.reset()

    def reset(self):
        self.board = chess.Board()
        self.moves = []
        self.locked = False

    def uci_position(self):
        return "position startpos" + (" moves " + " ".join(self.moves) if self.moves else "")

    def reconcile(self, target):
        if same_position(self.board, target):
            return "same"
        candidates = []
        for move in self.board.legal_moves:
            probe = self.board.copy()
            probe.push(move)
            if same_position(probe, target):
                candidates.append(move)
        if len(candidates) == 1:
            move = candidates[0]
            self.board.push(move)
            self.moves.append(move.uci())
            return "forward"
        rewind = self.board.copy()
        while rewind.move_stack:
            rewind.pop()
            if same_position(rewind, target):
                count = len(rewind.move_stack)
                self.board = rewind
                self.moves = self.moves[:count]
                return "rewind"
        return "missing"


def parse_fics_rating(token):
    """FICS ELO, ++++ (unrated), or None when not published."""
    if token is None:
        return None
    value = str(token).strip()
    return int(value) if value.isdigit() else "++++" if value == "++++" else None


def save_game_json(path, record):
    """Atomic append-with-replace, preserving previous games and avoiding duplicates."""
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        data = json.loads(target.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or not isinstance(data.get("partidas"), list):
            raise ValueError(f"Formato JSON no reconocido: {target}")
    else:
        data = {"schema_version": 1, "partidas": []}
    if any(g.get("id") == record["id"] for g in data["partidas"]):
        return False
    data["partidas"].append(record)
    temp = target.with_name(target.name + ".tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink()
    return True


class Bridge:
    def __init__(self, args):
        self.a = args
        self.events = queue.Queue()
        self.uci = self.fics = None
        self.username = None
        self.login = "waiting"
        self.fics_ready = self.uci_ok = self.uci_ready = False
        self.engine_name = "Desconocido"
        self.history = History()
        self.game_key = self.position = None
        self.search_fen = self.search_since = None
        self.stopping = False
        self.stop_since = None
        self.awaiting_confirmation = None
        self.challenge_name = None
        self.challenge_buffer = ""
        self.challenge_at = 0
        self.seeks = {}
        self.seek_pending = None
        self.seek_pending_since = None
        self.seek_retry_after = {}
        self.last_seek_refresh = 0
        self.seek_suspended = False
        self.uci_connecting = False
        self.uci_deadline = None
        self.uci_retry_at = None
        self.pending_challenge = None
        self.uci_last_error = None
        self.game_type = None
        self.game_time_control = None
        self.game_rated = None
        self.offer_type_pending = None
        self.offer_rated_pending = None
        self.challenge_type_pending = None
        self.challenge_rated_pending = None
        self.last_clock = None
        self.game_started = None
        self.game_started_utc = None
        self.ratings = {}
        self.ratings_pending = {}
        self.recorded_games = set()

    def capture_ratings(self, line):
        # FICS messages: Creating: white (1234) black (++++) rated blitz 5 0
        # or: Game 123: white (1234) black (1560) ...
        m = re.search(r"(?:Creating:|Game\s+\d+:)\s*([\w-]+)\s*\((\d+|\+{4}|----|Unr)\)\s+([\w-]+)\s*\((\d+|\+{4}|----|Unr)\)", line, re.I)
        if m:
            self.ratings_pending = {m.group(1).casefold(): parse_fics_rating(m.group(2)),
                                    m.group(3).casefold(): parse_fics_rating(m.group(4))}
            if self.game_key:
                names = {n.casefold() for n in self.game_key[1:]}
                if names == set(self.ratings_pending):
                    self.ratings.update(self.ratings_pending)

    def schedule_uci_retry(self, reason, recover=False):
        """Schedule one reconnect, keeping FICS and the current game alive."""
        # La recuperación de un bloqueo es obligatoria aun sin --retry.
        # --retry sigue controlando desconexiones ordinarias.
        delay = self.a.retry if self.a.retry is not None else (2.0 if recover else None)
        if delay is None:
            return
        self.uci_retry_at = time.monotonic() + delay
        log("🔄", "UCI", f"{reason}. Reintento de conexión en {delay:g} s")

    def retry_uci_tick(self):
        if self.uci_retry_at is None or time.monotonic() < self.uci_retry_at:
            return
        self.uci_retry_at = None
        if self.uci is None:
            log("🔄", "UCI", f"Reconectando a {self.a.ip}:{self.a.port}")
            self.ensure_uci()

    def recover_uci_stall(self, reason):
        """Hard reset of a stalled search/stop, preserving FICS and verified moves."""
        elapsed = (time.monotonic() - self.search_since
                   if self.search_since is not None else
                   time.monotonic() - self.stop_since
                   if self.stop_since is not None else 0.0)
        log("🚨", "UCI", f"WATCHDOG: {reason}; espera={elapsed:.2f}s; "
            f"partida={self.game_key[0] if self.game_key else '-'}; "
            f"ply={len(self.history.moves)}; "
            f"buscando={self.search_fen is not None}; stop_pendiente={self.stopping}; "
            f"reconectando TCP")
        self.disconnect_uci(reason=f"Reinicio forzado: {reason}")
        self.schedule_uci_retry("Recuperación automática UCI", recover=True)

    def uci_connection_lost(self, reason):
        """Prevent stale bestmoves and resume only after a new UCI handshake."""
        log("❌", "UCI", reason)
        self.disconnect_uci(reason="Conexión perdida")
        if self.a.retry is not None:
            self.schedule_uci_retry("Motor UCI desconectado")
        elif self.game_key is not None:
            log("⚠️", "PARTIDA", "Sin --retry: abandonando la partida")
            self.fics.send("resign")

    def ensure_uci(self):
        if self.uci is not None:
            return True
        try:
            self.uci = SocketLink("UCI", self.a.ip, self.a.port, self.events)
            self.uci_retry_at = None
            self.uci_ok = self.uci_ready = False
            self.uci_deadline = time.monotonic() + self.a.connect_timeout
            self.uci.send("uci")
            return True
        except OSError as exc:
            log("❌", "UCI", f"Sin conexión: {exc}")
            self.disconnect_uci(reason="Fallo durante conexión/handshake")
            self.schedule_uci_retry("Motor UCI inaccesible")
            return False

    def disconnect_uci(self, reason="Desconectado al terminar la partida"):
        old = self.uci
        self.uci = None
        self.uci_ok = self.uci_ready = False
        self.uci_deadline = None
        self.search_fen = self.search_since = None
        self.stopping = False
        self.stop_since = None
        if old:
            # No enviar 'quit' a un motor bloqueado: el envío puede bloquear.
            # shutdown() despierta recv() del hilo lector anterior.
            old.close()
            log("🔌", "UCI", reason)

    def handle_result(self, line):
        match = re.search(r"\{Game\s+(\d+)\s+.*?\}\s*(1-0|0-1|1/2-1/2|\*)", line)
        if not match:
            return False
        game, result = int(match.group(1)), match.group(2)
        reason_match = re.search(r"\{Game\s+\d+\s+(.+?)\}\s*(?:1-0|0-1|1/2-1/2|\*)", line)
        reason = reason_match.group(1).strip() if reason_match else "No informada"
        if self.game_key is None or self.game_key[0] != game:
            return False
        # Resumen de modalidad y últimos relojes informados por FICS.
        kind = self.game_type or "desconocida"
        tc = self.game_time_control or "?+?"
        rated = ("rated" if self.game_rated is True else
                 "unrated" if self.game_rated is False else "modalidad desconocida")
        log("🎮", "PARTIDA", f"#{game} {kind} | {rated} | {tc}")
        if self.last_clock and self.last_clock[0] == game:
            _, wms, bms = self.last_clock
            log("⏱️", "PARTIDA",
                f"#{game} último reloj FICS: ⚪ {format_clock(wms)} | ⚫ {format_clock(bms)}")
        else:
            log("⏱️", "PARTIDA", f"#{game} relojes finales no disponibles")
        # Mostrar los nombres como los comunica FICS, preservando mayúsculas.
        if self.position and self.position.get("game") == game:
            white = self.position["white"]
            black = self.position["black"]
        else:
            white, black = self.game_key[1:]

        def mark_player(player):
            if self.username and player.casefold() == self.username.casefold():
                return (f"\033[1;4m{player}\033[0m" if sys.stdout.isatty()
                        else f"__**{player}**__ [NOSOTROS]")
            return player

        log("♟️", "PARTIDA", f"#{game} ⚪ Blancas: {mark_player(white)} | ⚫ Negras: {mark_player(black)}")
        if result in ("1-0", "0-1"):
            winner = white if result == "1-0" else black
            ours = bool(self.username and winner.casefold() == self.username.casefold())
            outcome = "GANAMOS 🏆" if ours else "PERDIMOS"
            log("🏁", "PARTIDA", f"#{game} resultado {result} | ganador: {mark_player(winner)} | {outcome}")
        elif result == "1/2-1/2":
            log("🤝", "PARTIDA", f"#{game} resultado {result} | TABLAS")
        else:
            log("🏁", "PARTIDA", f"#{game} resultado * | partida sin resultado definitivo")
        # FICS recycles game numbers. Deduplicate by session-specific game identity.
        unique_game_id = f"{self.game_started_utc or 'unknown'}:{game}"
        if result != "*" and self.a.json and unique_game_id not in self.recorded_games:
            our_name = next((n for n in (white, black) if self.username and n.casefold() == self.username.casefold()), None)
            if our_name:
                our_white = our_name.casefold() == white.casefold()
                opponent = black if our_white else white
                score = 0.5 if result == "1/2-1/2" else (1.0 if (result == "1-0") == our_white else 0.0)
                elapsed = round(max(0.0, time.monotonic() - self.game_started), 3) if self.game_started is not None else None
                record = {
                    "id": unique_game_id,
                    "fics_game": game, "fecha_inicio_utc": self.game_started_utc,
                    "fecha_fin_utc": datetime.now(timezone.utc).isoformat(),
                    "usuario_propio": our_name, "elo_propio": self.ratings.get(our_name.casefold()),
                    "color_propio": "blancas" if our_white else "negras",
                    "usuario_contrincante": opponent, "elo_contrincante": self.ratings.get(opponent.casefold()),
                    "color_contrincante": "negras" if our_white else "blancas",
                    "resultado": score, "resultado_fics": result,
                    "razon": reason, "cantidad_movidas": (len(self.history.moves) + 1) // 2,
                    "cantidad_medias_jugadas": len(self.history.moves),
                    "tiempo_segundos": elapsed, "control_tiempo": self.game_time_control,
                    "modalidad": kind, "rated": self.game_rated,
                    "motor": self.engine_name,
                }
                try:
                    saved = save_game_json(self.a.json, record)
                    self.recorded_games.add(unique_game_id)
                    if saved:
                        log("💾", "JSON", f"Partida #{game} guardada en {self.a.json} (id={unique_game_id})")
                    else:
                        log("ℹ️", "JSON", f"Partida ya registrada (id={unique_game_id})")
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    log("❌", "JSON", f"No se pudo guardar partida #{game}: {exc}")
        self.reset_game()
        self.last_seek_refresh = 0
        return True

    def authenticated(self, name):
        if self.fics_ready:
            return
        self.username = name
        self.login = "authenticated"
        self.fics_ready = True
        log("👤", "FICS", f"Identidad asignada: {name}")
        for command in (
            "iset nowrap 1", "set style 12", "set seek 1",
            "iset seekremove 1", "iset seekinfo 1",
            "set shout 0", "set cshout 0",
            "set open 1",
        ):
            self.fics.send(command)
        self.last_seek_refresh = time.monotonic()
        log("📡", "SEEK", f"Anuncios activados: unrated standard, {self.a.min_time}-{self.a.max_time} min")
        if self.a.accept:
            self.fics.send("sought")

    def login_line(self, line):
        for pattern in (
            r'Logging you in as\s+"([^"]+)"',
            r"Starting FICS session as\s+([\w-]+)",
            r'Your name will be\s+"([^"]+)"',
        ):
            match = re.search(pattern, line, re.I)
            if match:
                self.authenticated(match.group(1))
                return
        if self.login == "waiting" and re.search(r"(?:login|username):\s*$", line, re.I):
            self.fics.send(self.a.user)
            self.login = "username_sent"
        elif self.login == "username_sent":
            if re.search(r"password:\s*$", line, re.I):
                self.fics.send(self.a.password, secret=True)
                self.login = "password_sent"
            elif self.a.user.lower() == "guest" and re.search(r"Press return to enter", line, re.I):
                self.fics.send("")
                self.login = "guest_confirmed"
        elif (self.a.user.lower() != "guest" and self.login == "password_sent"
              and re.search(r"fics%\s*$", line, re.I)):
            self.authenticated(self.a.user)

    def seek_clear(self, line):
        if not re.match(r"^\s*<sc>\s*$", line):
            return False
        self.seeks.clear()
        log("🔄", "SEEK", "Inventario reiniciado")
        return True

    def seek_remove(self, line):
        match = re.match(r"^\s*<sr>\s+([\d\s]+)$", line)
        if not match:
            return False
        for item in match.group(1).split():
            number = int(item)
            self.seeks.pop(number, None)
            log("🗑️", "SEEK", f"Retirada oferta #{number}")
        return True

    def seek_text_offer(self, line):
        """Anuncios humanos, por ejemplo: Name (++++) seeking 3 0 unrated blitz ("play 25" to respond)."""
        match = re.search(
            r"(?P<user>[A-Za-z][\w-]*)\s+\([^)]*\)\s+seeking\s+"
            r"(?P<minutes>\d+)\s+(?P<increment>\d+)\s+"
            r"(?P<rating>unrated|rated)\s+(?P<kind>[A-Za-z]+)"
            r".*?\bplay\s+(?P<number>\d+)", line, re.I,
        )
        if not match:
            return False
        m = match.groupdict()
        number = int(m["number"])
        kind = m["kind"].lower()
        kind = {"bullet": "lightning", "classical": "standard"}.get(kind, kind)
        self.seeks[number] = dict(
            number=number, player=m["user"], minutes=int(m["minutes"]),
            increment=int(m["increment"]), rated=m["rating"].lower() == "rated",
            type=kind, received=time.monotonic(),
        )
        log("📢", "SEEK", f"#{number} {m['user']} {m['minutes']}+{m['increment']} "
            f"{m['rating']} {m['kind']}")
        self.choose_seek()
        return True

    def seek_offer(self, line):
        match = re.match(r"^\s*<s>\s+(\d+)\s+(.*)$", line)
        if not match:
            return False
        number = int(match.group(1))
        fields = {k.lower(): v for k, v in re.findall(r"([a-z]+)=([^\s]+)", match.group(2), re.I)}
        if any(key not in fields for key in ("w", "t", "i", "r", "tp")):
            log("⚠️", "SEEK", f"Oferta #{number} incompleta")
            return True
        try:
            offer = {
                "number": number, "player": fields["w"],
                "minutes": int(fields["t"]), "increment": int(fields["i"]),
                "rated": fields["r"].lower() == "r",
                "type": fields["tp"].lower(),
                "received": time.monotonic(),
            }
        except ValueError:
            log("⚠️", "SEEK", f"Campos inválidos en oferta #{number}")
            return True
        self.seeks[number] = offer
        label = "rated" if offer["rated"] else "unrated"
        log("📢", "SEEK", f"#{number} {offer['player']} {offer['minutes']}+{offer['increment']} {label} {offer['type']}")
        self.choose_seek()
        return True

    def eligible_seek(self, offer):
        return (
            self.a.accept
            and (self.a.rated if offer["rated"] else self.a.unrated)
            and offer["type"] in self.a.types
            and self.a.min_time <= offer["minutes"] <= self.a.max_time
            and 0 <= offer["increment"] <= self.a.max_increment
            and (not self.username or offer["player"].lower() != self.username.lower())
            and time.monotonic() >= self.seek_retry_after.get(offer["number"], 0)
        )

    def choose_seek(self):
        if (not self.a.accept or not self.fics_ready or self.game_key is not None
                or self.seek_pending is not None or self.seek_suspended
                or self.challenge_name is not None):
            return
        offers = [offer for offer in self.seeks.values() if self.eligible_seek(offer)]
        if not offers:
            return
        offers.sort(key=lambda o: (-o["minutes"], -o["increment"], o["received"]))
        offer = offers[0]
        number = offer["number"]
        self.offer_type_pending = offer["type"]
        self.offer_rated_pending = offer["rated"]
        self.seek_pending = number
        self.seek_pending_since = time.monotonic()
        if not self.ensure_uci():
            self.release_seek("Servidor UCI inaccesible")
            return
        log("🎯", "SEEK", f"Intentando #{number}: {offer['player']} {offer['minutes']}+{offer['increment']}")
        if self.uci_ready:
            self.fics.send(f"play {number}")
        else:
            log("⏳", "UCI", "Esperando readyok antes de play")

    def release_seek(self, reason, cooldown=True):
        number = self.seek_pending
        if number is None:
            return
        log("ℹ️", "SEEK", f"#{number}: {reason}")
        if cooldown:
            self.seek_retry_after[number] = time.monotonic() + 120
        self.seek_pending = self.seek_pending_since = None

    def seek_response(self, line):
        if self.seek_pending is None:
            return False
        low = line.lower()
        errors = (
            "bad index", "no such ad", "no longer available",
            "cannot accept seeks", "can't accept seeks",
            "not eligible", "does not fit", "not accepting",
            "you are already playing", "not available",
        )
        if not any(item in low for item in errors):
            return False
        restricted = "cannot accept seeks" in low or "can't accept seeks" in low
        self.release_seek(f"FICS rechazó play: {line}")
        if restricted:
            self.seek_suspended = True
            log("🚫", "SEEK", "La cuenta no puede aceptar ofertas seek ajenas")
        self.choose_seek()
        return True

    def seek_tick(self):
        if not self.a.accept or not self.fics_ready or self.game_key is not None:
            return
        now = time.monotonic()
        if self.seek_pending is not None and self.seek_pending_since is not None:
            if now - self.seek_pending_since >= self.a.seek_timeout:
                self.release_seek("Timeout esperando confirmación")
        if self.seek_pending is None and now - self.last_seek_refresh >= self.a.seek_retry:
            self.last_seek_refresh = now
            self.fics.send("sought")
        self.choose_seek()

    def challenge_line(self, line):
        if not self.a.accept or not self.fics_ready or self.game_key is not None or self.seek_pending is not None:
            return
        m = re.search(r"\bChallenge:\s*([A-Za-z][\w-]*)", line, re.I)
        if m:
            self.challenge_name = m.group(1)
            self.challenge_buffer = line
            self.challenge_at = time.monotonic()
        elif self.challenge_name:
            if time.monotonic() - self.challenge_at > 3:
                self.challenge_name = None
                self.challenge_buffer = ""
                return
            self.challenge_buffer += " " + line
        else:
            return
        terms = self.challenge_buffer.lower()
        if not re.search(r"\b(?:rated|unrated)\b", terms):
            return
        kind = next((t for t in self.a.types if re.search(r"\b" + re.escape(t) + r"\b", terms)), None)
        rated = bool(re.search(r"\brated\b", terms)) and not bool(re.search(r"\bunrated\b", terms))
        compatible = (
            self.a.accept
            and (self.a.rated if rated else self.a.unrated)
            and kind is not None
            and not re.search(r"\b(?:wild|bughouse|crazyhouse|atomic|suicide|losers|chess960)\b", terms)
        )
        if compatible:
            self.challenge_type_pending = kind
            self.challenge_rated_pending = rated
            who = self.challenge_name
            if not self.ensure_uci():
                log("🚫", "BRIDGE", "Motor UCI inaccesible: rechazo")
                self.fics.send(f"decline {who}")
            elif self.uci_ready:
                log("🤝", "BRIDGE", f"Aceptando desafío de {who}")
                self.fics.send(f"accept {who}")
            else:
                self.pending_challenge = who
        else:
            log("🚫", "BRIDGE", f"Rechazando desafío de {self.challenge_name}")
            self.fics.send(f"decline {self.challenge_name}")
        self.challenge_name = None
        self.challenge_buffer = ""

    def cancel_search(self, reason):
        if self.search_fen is not None and self.uci is not None:
            log("🛑", "SYNC", reason)
            self.uci.send("stop")
            self.stopping = True
            self.stop_since = time.monotonic()
            self.search_fen = self.search_since = None

    def reset_game(self):
        self.cancel_search("Cambio/finalización de partida")
        self.game_key = self.position = None
        self.awaiting_confirmation = None
        self.history.reset()
        self.disconnect_uci()

    def lock_history(self, reason):
        if self.history.locked:
            return
        log("🚨", "SYNC", reason)
        self.history.locked = True
        self.cancel_search("Historial no verificado")
        log("🔒", "SYNC", "Bloqueada la emisión de movimientos")
        self.fics.send("moves")

    def position_line(self, line):
        try:
            pos = style12(line)
        except ValueError as exc:
            log("⚠️", "BRIDGE", str(exc))
            return
        if not self.fics_ready or not self.username or pos["relation"] not in (-1, 1):
            return
        white, black = pos["white"].lower(), pos["black"].lower()
        name = self.username.lower()
        if name not in (white, black):
            return
        my_color = chess.WHITE if name == white else chess.BLACK
        key = (pos["game"], white, black)
        if key != self.game_key:
            if self.seek_pending is not None:
                self.release_seek("Partida iniciada", cooldown=False)
            self.seeks.clear()
            # Conservar la conexión negociada al aceptar play/challenge.
            # Solo desconectar si realmente finaliza otra partida.
            if self.game_key is not None:
                self.reset_game()
            else:
                self.history.reset()
            if not self.ensure_uci():
                if self.a.retry is None:
                    log("🚫", "PARTIDA", "No hay motor; solicitando abort")
                    self.fics.send("abort")
                    return
                log("⏳", "PARTIDA", "Motor sin conexión; se intentará recuperar")
            self.game_key = key
            self.game_started = time.monotonic()
            self.game_started_utc = datetime.now(timezone.utc).isoformat()
            self.ratings = {name: self.ratings_pending.get(name) for name in (white, black)}
            self.position = pos
            self.game_type = (self.offer_type_pending or self.challenge_type_pending or
                              classify_game(pos["initial_minutes"], pos["increment"] // 1000))
            self.game_rated = (self.offer_rated_pending if self.offer_type_pending else
                               self.challenge_rated_pending if self.challenge_type_pending else None)
            self.game_time_control = f'{pos["initial_minutes"]}+{pos["increment"] // 1000}'
            self.last_clock = (pos["game"], pos["wtime"], pos["btime"])
            self.offer_type_pending = self.challenge_type_pending = None
            self.offer_rated_pending = self.challenge_rated_pending = None
            bold = "\033[1;4m" if sys.stdout.isatty() else "**"
            normal = "\033[0m" if sys.stdout.isatty() else "**"
            def player(who):
                return f"{bold}{who}{normal}" if who.lower() == name else who
            log("♟️", "PARTIDA", f"#{pos['game']} ⚪ Blancas: {player(pos['white'])} | ⚫ Negras: {player(pos['black'])}")
            if not same_position(self.history.board, pos["board"]):
                self.lock_history("Partida iniciada fuera de startpos; historial no reconstruible")
                return
            log("✅", "SYNC", "Posición inicial verificada")
            if self.uci_ok:
                self.uci_ready = False
                self.uci.send("ucinewgame")
                self.uci.send("isready")
            return
        self.position = pos
        self.last_clock = (pos["game"], pos["wtime"], pos["btime"])
        if self.history.locked:
            return
        status = self.history.reconcile(pos["board"])
        if status == "missing":
            self.lock_history("Saltos de movimientos / posición divergente")
            return
        if status == "forward":
            log("✅", "SYNC", f"Confirmado {self.history.moves[-1]} | ply={len(self.history.moves)}", detail=True)
        elif status == "rewind":
            log("↩️", "SYNC", "Retroceso confirmado")
            self.cancel_search("Takeback")
            self.awaiting_confirmation = None
        if self.awaiting_confirmation:
            latest = self.history.moves[-1] if self.history.moves else None
            if latest == self.awaiting_confirmation:
                self.awaiting_confirmation = None
                log("✅", "SYNC", f"FICS confirmó {latest}")
            elif status != "same":
                self.lock_history("FICS no confirmó nuestra jugada")
                return
        if self.search_fen and self.search_fen != self.history.board.fen():
            self.cancel_search("Cambió el tablero durante la búsqueda")
        if self.history.board.turn == my_color:
            self.maybe_search()

    def maybe_search(self):
        pos = self.position
        if (pos is None or self.game_key is None or self.history.locked
                or not self.uci_ok or not self.uci_ready or self.stopping
                or self.search_fen is not None or self.awaiting_confirmation is not None):
            return
        my_color = chess.WHITE if self.username.lower() == pos["white"].lower() else chess.BLACK
        if self.history.board.turn != my_color:
            return
        self.uci.send(self.history.uci_position())
        if self.a.movetime:
            self.uci.send(f"go movetime {self.a.movetime}")
        else:
            self.uci.send(
                f"go wtime {pos['wtime']} btime {pos['btime']} "
                f"winc {pos['increment']} binc {pos['increment']}"
            )
        self.search_fen = self.history.board.fen()
        self.search_since = time.monotonic()
        log("🧠", "UCI", f"Búsqueda | ply={len(self.history.moves)}")

    def engine_line(self, line):
        if line:
            # UCI info de búsqueda es telemetría operativa obligatoria.
            # No confundirla con "info string" (depuración).
            # Show every UCI search metric, even with --verbose disabled.
            # Engines may emit nodes/time/score on separate 'info' lines.
            is_metrics = line.startswith("info ") and bool(re.search(
                r"\b(?:nodes\s+\d+|time\s+\d+|score\s+(?:cp\s+-?\d+|mate\s+-?\d+)|nps\s+\d+)\b",
                line,
            ))
            log("🧠", "UCI", line,
                detail=(line.startswith("info ") and not is_metrics) or not line)
        if line.startswith("id name "):
            self.engine_name = normalize_brain_name(line[8:])
        elif line.strip() == "uciok":
            self.uci_ok = True
            if self.game_key is not None:
                self.uci.send("ucinewgame")
            self.uci.send("isready")
        elif line.strip() == "readyok":
            self.uci_ready = True
            self.uci_deadline = None
            if self.pending_challenge:
                who = self.pending_challenge
                self.pending_challenge = None
                self.fics.send(f"accept {who}")
            elif self.seek_pending is not None and self.game_key is None:
                self.fics.send(f"play {self.seek_pending}")
            self.maybe_search()
        elif line.startswith("bestmove "):
            match = re.match(r"bestmove\s+(\S+)", line)
            if not match:
                return
            if self.stopping:
                self.stopping = False
                self.stop_since = None
                self.uci_ready = False
                self.uci.send("isready")
                return
            if self.search_fen is None or self.history.locked:
                return
            move_text = match.group(1).lower()
            fen = self.search_fen
            self.search_fen = self.search_since = None
            if fen != self.history.board.fen():
                self.lock_history("bestmove obsoleto")
                return
            if move_text in ("(none)", "0000"):
                self.lock_history("Motor devolvió bestmove vacío")
                return
            try:
                move = chess.Move.from_uci(move_text)
            except ValueError:
                self.lock_history(f"Formato UCI inválido: {move_text}")
                return
            if move not in self.history.board.legal_moves:
                self.lock_history(f"Jugada UCI ilegal: {move_text}")
                return
            # FICS requiere SAN para promociones; conservar UCI en el historial.
            san_move = self.history.board.san(move)
            self.awaiting_confirmation = move.uci()
            self.fics.send(san_move)
            log("⏳", "SYNC", f"Enviada {move.uci()} como {san_move}; esperando FICS", detail=True)

    def fics_line(self, line):
        if line:
            self.capture_ratings(line)
            log("🌐", "FICS", line, detail=(line.strip() == "fics%" or line.startswith("<12> ")))
        elif VERBOSE:
            log("🌐", "FICS", "", detail=True)
        # Rechazo de una jugada enviada: no continuar hasta recuperar sincronía.
        if (self.awaiting_confirmation is not None
                and re.search(r"(?:command not found|illegal move|invalid move|ambiguous move|not your move)", line, re.I)):
            rejected = self.awaiting_confirmation
            self.awaiting_confirmation = None
            self.lock_history(f"FICS rechazó {rejected}: {line.strip()}")
            return
        if not self.fics_ready:
            if re.search(r"invalid password|invalid login|already logged in", line, re.I):
                raise RuntimeError(f"FICS rechazó login: {line}")
            self.login_line(line)
        if self.seek_clear(line) or self.seek_remove(line) or self.seek_offer(line) or self.seek_text_offer(line) or self.seek_response(line):
            return
        if line.startswith("<12> "):
            self.position_line(line)
            return
        self.challenge_line(line)
        if self.handle_result(line):
            return
        if re.search(r"\{Game\s+\d+.*\}\s+(?:1-0|0-1|1/2-1/2|\*)", line):
            log("✅", "PARTIDA", "Partida finalizada")
            self.reset_game()
            self.last_seek_refresh = 0

    def run(self):
        log("🚀", "APP", f"fics_uci v{VERSION}")
        try:
            self.fics = SocketLink("FICS", self.a.ip_fics, self.a.port_fics, self.events, telnet=True)
            while True:
                try:
                    source, link, line = self.events.get(timeout=0.25)
                except queue.Empty:
                    source = None
                if source:
                    # Descartar datos del socket anterior luego de reconectar.
                    if link is not (self.uci if source == "UCI" else self.fics):
                        continue
                    if line == "__DISCONNECT__":
                        if source == "UCI":
                            if self.uci is not None:
                                self.uci_connection_lost("Conexión TCP cerrada")
                            continue
                        raise ConnectionError(f"Conexión cerrada: {source}")
                    if line.startswith("__ERROR__"):
                        if source == "UCI":
                            if self.uci is not None:
                                self.uci_connection_lost(line)
                            continue
                        raise ConnectionError(f"{source}: {line}")
                    if source == "UCI":
                        self.engine_line(line)
                    elif source == "FICS":
                        self.fics_line(line)
                if (self.search_since is not None
                        and time.monotonic() - self.search_since > self.a.engine_timeout):
                    self.recover_uci_stall("Timeout bestmove sin respuesta")
                if (self.stopping and self.stop_since is not None
                        and time.monotonic() - self.stop_since > self.a.stop_timeout):
                    self.recover_uci_stall("Timeout esperando bestmove tras stop")
                self.retry_uci_tick()
                self.maybe_search()
                self.seek_tick()
                if self.uci_deadline and time.monotonic() > self.uci_deadline:
                    log("❌", "UCI", "Timeout de inicialización")
                    if self.pending_challenge:
                        self.fics.send(f"decline {self.pending_challenge}")
                        self.pending_challenge = None
                    self.release_seek("Motor UCI sin readyok")
                    self.disconnect_uci(reason="Timeout de inicialización")
                    self.schedule_uci_retry("Handshake UCI agotado")
        finally:
            for conn in (self.uci, self.fics):
                if conn:
                    try:
                        conn.send("quit")
                    except OSError:
                        pass
                    conn.close()


def main():
    p = argparse.ArgumentParser(description="FICS↔UCI TCP · configuración YAML")
    p.add_argument("--config", default=None)
    p.add_argument("--json", default=None, help="Archivo JSON acumulativo de partidas terminadas")
    p.add_argument("--stop-timeout", type=float, default=None,
                   help="Segundos máximos para recibir bestmove tras stop (default 5)")
    p.add_argument("--retry", type=float, default=None,
                   help="Reintentar conexión TCP al motor UCI tras NN segundos; omitido: no reintentar")
    p.add_argument("--verbose", nargs="?", const=True, type=lambda x: str(x).lower() in ("true", "yes", "1", "on"), default=None)
    for option in ("ip", "ip_fics", "user", "password"):
        p.add_argument("--" + option, "--" + option.replace("_", "-"), default=None)
    for option in ("port", "port_fics", "movetime", "min_time", "max_time", "max_increment"):
        p.add_argument("--" + option, "--" + option.replace("_", "-"), type=int, default=None)
    for option in ("engine_timeout", "connect_timeout", "seek_timeout", "seek_retry"):
        p.add_argument("--" + option, "--" + option.replace("_", "-"), type=float, default=None)
    def boolean(text):
        if isinstance(text, bool):
            return text
        if str(text).lower() in ("true", "1", "yes", "on"):
            return True
        if str(text).lower() in ("false", "0", "no", "off"):
            return False
        raise argparse.ArgumentTypeError("Se esperaba true/false")
    for key in ("accept", "rated", "unrated"):
        p.add_argument("--" + key, nargs="?", const=True, type=boolean, default=None)
    p.add_argument("--types", nargs="+", default=None,
                   help="FICS: standard blitz lightning bullet classical untimed")
    a = p.parse_args()
    config_file = Path(a.config) if a.config else Path(__file__).resolve().parent / "config.yml"
    config = {}
    if config_file.exists():
        config = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        if not isinstance(config, dict):
            p.error("config.yml debe contener un mapa YAML")
    defaults = dict(ip="127.0.0.1", port=6110, ip_fics="freechess.org", port_fics=5000,
                    user="guest", password="", accept=True, rated=True, unrated=True, verbose=False,
                    types=["standard", "blitz", "lightning", "bullet", "classical"],
                    movetime=0, engine_timeout=90.0, connect_timeout=15.0,
                    min_time=0, max_time=180, max_increment=180, seek_timeout=15.0, seek_retry=60.0)
    for key, default in defaults.items():
        value = getattr(a, key)
        if value is None:
            value = config.get(key, default)
        if key in ("accept", "rated", "unrated", "verbose"):
            value = boolean(value)
        setattr(a, key, value)
    if a.stop_timeout is None:
        a.stop_timeout = config.get("stop_timeout", 5.0)
    try:
        a.stop_timeout = float(a.stop_timeout)
    except (TypeError, ValueError):
        p.error("--stop-timeout debe ser un número positivo")
    if not (0 < a.stop_timeout < float("inf")):
        p.error("--stop-timeout debe ser positivo y finito")
    if a.json is None:
        a.json = config.get("json")
    if a.retry is None:
        a.retry = config.get("retry")
    if a.retry is not None:
        try:
            a.retry = float(a.retry)
        except (TypeError, ValueError):
            p.error("--retry debe ser un número positivo de segundos")
        if not (0 < a.retry < float("inf")):
            p.error("--retry debe ser un número positivo y finito")
    if isinstance(a.types, str):
        a.types = [s.strip().lower() for s in a.types.split(",") if s.strip()]
    else:
        a.types = [str(t).lower() for t in a.types]
    # Bullet y classical son alias de clases de tiempo, no valores tp independientes
    aliases = {"classical":"standard", "bullet":"lightning"}
    a.types = set(aliases.get(t,t) for t in a.types)
    if a.min_time < 0 or a.max_time < a.min_time or a.max_increment < 0:
        p.error("Rango de tiempo inválido")
    if min(a.engine_timeout, a.connect_timeout, a.seek_timeout, a.seek_retry) <= 0:
        p.error("Timeouts inválidos")
    if not a.password and a.user.lower() != "guest":
        log("🔐", "FICS", "Se enviará contraseña vacía (configurada)")
    global VERBOSE
    VERBOSE = a.verbose
    log("⚙️", "APP", f"Verbose={'ON' if VERBOSE else 'OFF'}")
    try:
        Bridge(a).run()
    except KeyboardInterrupt:
        log("🛑", "APP", "Interrumpido")
    except (OSError, RuntimeError) as exc:
        log("❌", "APP", str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
