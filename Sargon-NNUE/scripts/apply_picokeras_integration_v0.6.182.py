"""Apply picoKeras integration to the current Sargon-NNUE checkout.

Run from anywhere: python scripts/apply_picokeras_integration_v0.6.182.py
The patch is strictly anchored; if any upstream file diverges, abort before writing.
"""
from __future__ import annotations

from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / 'src' / 'sargon_nnue'


def replace_once(text, before, after, filename):
    n = text.count(before)
    if n != 1:
        raise RuntimeError(f'{filename}: se esperaba una coincidencia para {before!r}, encontradas {n}')
    return text.replace(before, after, 1)


def update(name, operations):
    path = PKG / name
    content = path.read_text(encoding='utf-8')
    new = content
    for before, after in operations:
        if after in new:
            continue  # idempotence for an already applied individual change
        new = replace_once(new, before, after, name)
    ast.parse(new, filename=str(path))
    return path, new


changes = [
 ('brains.py', [
   ("PLAYER_CHOICES = ('random','sargon','sargon-plus','cerebrum','stockfish','sunfish','external','alphazero','lc0','doc','picosargon','picoalpha','alphazero-x86','AlphaZero-X86')", "PLAYER_CHOICES = ('random','sargon','sargon-plus','cerebrum','stockfish','sunfish','external','alphazero','lc0','doc','picosargon','picoalpha','picokeras','picoKeras','alphazero-x86','AlphaZero-X86')"),
   ("if player in ('stockfish','sunfish','external','lc0','picosargon','picoalpha','alphazero-x86','AlphaZero-X86'):", "if player in ('stockfish','sunfish','external','lc0','picosargon','picoalpha','picokeras','alphazero-x86','AlphaZero-X86'):"),
   ("if player=='picoalpha': allowed.add('model')", "if player=='picoalpha': allowed.add('model')\n        if player=='picokeras': allowed|={'network','tmax'}"),
   ("if player=='picoalpha' and ev!='null':", "if player=='picokeras' and ev!='null':raise ValueError('player picokeras requiere evaluator null')\n    if player=='picokeras' and not config.get('engine-path'):raise ValueError('player picokeras requiere engine-path')\n    if player=='picokeras' and not config.get('network'):raise ValueError('player picokeras requiere network')\n    if player=='picoalpha' and ev!='null':"),
   ("if player not in ('stockfish','random','lc0','picosargon','external','picoalpha','alphazero-x86','AlphaZero-X86') and ev=='null':", "if player not in ('stockfish','random','lc0','picosargon','external','picoalpha','picokeras','alphazero-x86','AlphaZero-X86') and ev=='null':"),
 ]),
 ('cli_common.py', [
   ('"picosargon", "picoalpha", "AlphaZero-X86"', '"picosargon", "picoalpha", "picokeras", "picoKeras", "AlphaZero-X86"'),
 ]),
 ('factory.py', [
   ('"picosargon", "external", "picoalpha", "alphazero-x86"', '"picosargon", "external", "picoalpha", "picokeras", "alphazero-x86"'),
 ]),
 ('players/__init__.py', [
   ('    if key == "picoalpha":', '    if key == "picokeras":\n        from .picokeras_uci import PicoKerasUCIPlayer\n        return PicoKerasUCIPlayer(engine_path, network, timeout_ms=timeout_ms, tmax_ms=tmax_ms)\n    if key == "picoalpha":'),
 ]),
 ('sargon_match.py', [
   ("if player in ('stockfish','lc0','picosargon','external','picoalpha','alphazero-x86') and ev not in", "if player in ('stockfish','lc0','picosargon','external','picoalpha','picokeras','alphazero-x86') and ev not in"),
   ("if ev=='null' and player not in ('stockfish','lc0','random','picosargon','external','picoalpha','alphazero-x86'):", "if ev=='null' and player not in ('stockfish','lc0','random','picosargon','external','picoalpha','picokeras','alphazero-x86'):"),
 ]),
 ('uci.py', [
   ('"EXTERNAL","ALPHAZERO-X86")', '"EXTERNAL","PICOKERAS","ALPHAZERO-X86")'),
 ]),
]

# Prepare the entire patch in memory before changing a single file.
output = []
try:
    for name, operations in changes:
        output.append(update(name, operations))
except Exception as exc:
    print(f'[picoKeras] NO SE APLICÓ el parche: {exc}', file=sys.stderr)
    raise SystemExit(1)

for path, content in output:
    path.write_text(content, encoding='utf-8')
    print(f'[picoKeras] OK {path.relative_to(ROOT)}')
print('[picoKeras] PATCH APPLIED; python -m compileall -q src/sargon_nnue')
