
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Actualización incremental fics_uci.py v0.2.0 -> v0.2.1."""

from pathlib import Path
import ast

SOURCE = Path("fics_uci.py")
TARGET = Path("fics_uci_v0.2.1.py")

source = SOURCE.read_text(encoding="utf-8")

if 'VERSION = "0.2.0"' not in source:
    raise SystemExit("Se esperaba la línea de base v0.2.0")

def replace_once(old, new):
    global source
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Reemplazo ambiguo: {count} ocurrencias de {old!r}"
        )
    source = source.replace(old, new, 1)


replace_once(
    'VERSION = "0.2.0"',
    'VERSION = "0.2.1"'
)

replace_once(
    '"wtime": max(0, int(p[23])) * 1000,',
    '"wtime": max(0, int(p[23])),'
)
replace_once(
    '"btime": max(0, int(p[24])) * 1000,',
    '"btime": max(0, int(p[24])),'
)

replace_once(
    '        self.challenge_at = 0\n',
    '''        self.challenge_at = 0

        # Gestor de anuncios FICS
        self.seeks = {}
        self.seek_pending = None
        self.seek_pending_since = None
        self.seek_retry_after = {}
        self.last_seek_refresh = 0.0
        self.seek_suspended = False
'''
)

replace_once(
    '''            "set seek 1",
            "set shout 0",''',
    '''            "set seek 1",
            "iset seekremove 1",
            "iset seekinfo 1",
            "set shout 0",'''
)

replace_once(
    '        log("✅", "FICS", "Esperando partidas unrated estándar")',
    '''        log("✅", "FICS", "Esperando partidas unrated estándar")
        log("📡", "SEEK", "Anuncios estructurados habilitados")
        self.last_seek_refresh = time.monotonic()
        self.fics.send("sought")'''
)

methods = '''
    def seek_clear(self, line):
        if not re.match(r"^\\\\s*<sc>\\\\s*$", line):
            return False

        self.seeks.clear()
        log("🔄", "SEEK", "Lista de anuncios reiniciada")
        return True

    def seek_remove(self, line):
        m = re.match(r"^\\\\s*<sr>\\\\s+([\\\\d\\\\s]+)$", line)
        if not m:
            return False

        for item in m.group(1).split():
            number = int(item)
            self.seeks.pop(number, None)
            log("🗑️", "SEEK", f"Retirado #{number}")

            # La retirada puede ser consecuencia de nuestro
            # play. Esperar confirmación o timeout.
        return True

    def seek_offer(self, line):
        m = re.match(
            r"^\\\\s*<s>\\\\s+(\\\\d+)\\\\s+(.*)$", line
        )
        if not m:
            return False

        number = int(m.group(1))
        fields = dict(re.findall(
            r"([a-z]+)=([^\\\\s]+)",
            m.group(2), re.I
        ))

        required = ("w", "t", "i", "r", "tp")
        if any(key not in fields for key in required):
            log("⚠️", "SEEK",
                f"Anuncio #{number} incompleto")
            return True

        try:
            offer = {
                "number": number,
                "player": fields["w"],
                "minutes": int(fields["t"]),
                "increment": int(fields["i"]),
                "rated": fields["r"].lower() == "r",
                "type": fields["tp"].lower(),
                "color": fields.get("c", "?"),
                "received": time.monotonic()
            }
        except ValueError:
            log("⚠️", "SEEK",
                f"Campos inválidos en #{number}")
            return True

        self.seeks[number] = offer

        rated = "rated" if offer["rated"] else "unrated"

        log("📢", "SEEK",
            f"#{number} {offer['player']} | "
            f"{offer['minutes']}+{offer['increment']} | "
            f"{rated} {offer['type']}")

        self.choose_seek()
        return True

    def eligible_seek(self, offer):
        if offer["rated"]:
            return False

        if offer["type"] not in (
            "standard", "blitz", "lightning"
        ):
            return False

        if not (
            self.a.min_time <= offer["minutes"]
            <= self.a.max_time
        ):
            return False

        if not (
            0 <= offer["increment"]
            <= self.a.max_increment
        ):
            return False

        if self.username and (
            offer["player"].lower()
            == self.username.lower()
        ):
            return False

        if time.monotonic() < self.seek_retry_after.get(
            offer["number"], 0
        ):
            return False

        return True

    def choose_seek(self):
        if not self.fics_ready:
            return

        if self.game_key is not None:
            return

        if self.seek_pending is not None:
            return

        if self.seek_suspended:
            return

        candidates = [
            offer for offer in self.seeks.values()
            if self.eligible_seek(offer)
        ]

        if not candidates:
            return

        # Se prioriza tiempo de reflexión disponible.
        candidates.sort(
            key=lambda x: (
                -x["minutes"],
                -x["increment"],
                x["received"]
            )
        )

        offer = candidates[0]
        number = offer["number"]

        self.seek_pending = number
        self.seek_pending_since = time.monotonic()

        log("🎯", "SEEK",
            f"Intentando #{number}: "
            f"{offer['player']} "
            f"{offer['minutes']}+{offer['increment']}")

        self.fics.send(f"play {number}")

    def release_seek(self, reason, cooldown=True):
        number = self.seek_pending
        if number is None:
            return

        log("ℹ️", "SEEK",
            f"Solicitud #{number}: {reason}")

        if cooldown:
            self.seek_retry_after[number] = (
                time.monotonic() + 120
            )

        self.seek_pending = None
        self.seek_pending_since = None

    def seek_response(self, line):
        if self.seek_pending is None:
            return False

        low = line.lower()

        errors = (
            "bad index",
            "no such ad",
            "no longer available",
            "cannot accept seeks",
            "can't accept seeks",
            "not eligible",
            "does not fit",
            "not accepting",
            "you are already playing",
            "not available",
        )

        if any(error in low for error in errors):
            restricted = (
                "cannot accept seeks" in low
                or "can't accept seeks" in low
            )

            self.release_seek(
                f"FICS rechazó play: {line}"
            )

            if restricted:
                self.seek_suspended = True
                log("🚫", "SEEK",
                    "FICS restringe la aceptación "
                    "de ofertas para esta cuenta")

            self.choose_seek()
            return True

        return False

    def seek_tick(self):
        if not self.fics_ready:
            return

        if self.game_key is not None:
            return

        now = time.monotonic()

        if self.seek_pending is not None:
            if (
                self.seek_pending_since is not None
                and now - self.seek_pending_since
                >= self.a.seek_timeout
            ):
                self.release_seek(
                    "Sin confirmación de FICS"
                )

        if (
            self.seek_pending is None
            and now - self.last_seek_refresh
            >= self.a.seek_retry
        ):
            self.last_seek_refresh = now
            self.fics.send("sought")

        self.choose_seek()
'''

# Los métodos se insertan antes de fics_line().
replace_once(
    '    def fics_line(self, line):',
    methods + '\n    def fics_line(self, line):'
)

replace_once(
    '''        if line.startswith("<12> "):
            self.position_line(line)
            return''',
    '''        if self.seek_clear(line):
            return

        if self.seek_remove(line):
            return

        if self.seek_offer(line):
            return

        if self.seek_response(line):
            return

        if line.startswith("<12> "):
            self.position_line(line)
            return'''
)

# Al comenzar una partida queda confirmada la aceptación.
replace_once(
    '''        if key != self.game_key:
            self.reset_game()
            self.game_key = key''',
    '''        if key != self.game_key:
            if self.seek_pending is not None:
                self.release_seek(
                    "Partida iniciada", cooldown=False
                )
            self.seeks.clear()
            self.reset_game()
            self.game_key = key'''
)

# La búsqueda de nuevos anuncios se reactiva al terminar.
replace_once(
    '''            log("🏁", "FICS", "Partida finalizada")
            self.reset_game()''',
    '''            log("🏁", "FICS", "Partida finalizada")
            self.reset_game()
            self.last_seek_refresh = 0.0
            self.choose_seek()'''
)

replace_once(
    '''                self.maybe_search()

        finally:''',
    '''                self.maybe_search()
                self.seek_tick()

        finally:'''
)

replace_once(
    '''    p.add_argument("--engine-timeout", type=float, default=90)

    a = p.parse_args()''',
    '''    p.add_argument("--engine-timeout", type=float, default=90)
    p.add_argument("--min-time", type=int, default=3)
    p.add_argument("--max-time", type=int, default=30)
    p.add_argument("--max-increment", type=int, default=60)
    p.add_argument("--seek-timeout", type=float, default=15)
    p.add_argument("--seek-retry", type=float, default=60)

    a = p.parse_args()

    if not (0 < a.min_time <= a.max_time):
        p.error("Rango de minutos inválido")
    if a.max_increment < 0:
        p.error("Incremento máximo inválido")
    if a.seek_timeout <= 0 or a.seek_retry <= 0:
        p.error("Tiempos seek inválidos")'''
)

# El parche debe conservar sintaxis válida.
ast.parse(source, filename=str(TARGET))

TARGET.write_text(source, encoding="utf-8")

print(f"✅ Generado: {TARGET}")
print(f"📦 Tamaño: {TARGET.stat().st_size} bytes")
print("🔎 Validación sintáctica superada")
print("⚠️ Pruebas de integración FICS/UCI pendientes")

