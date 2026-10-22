#!/usr/bin/env python3
"""Parche puntual para MATCH, sin reemplazar el resto del fuente local."""
import ast
from pathlib import Path
import re
import shutil

root=Path(__file__).resolve().parents[1]
path=root/'src/sargon_nnue/sargon_match.py'
source=path.read_text(encoding='utf-8-sig')
checks=[
    (r"(?m)^(\s*if player in )\(([^\n)]*)\)( and ev not in \('null',None\):ap\.error\(f'--\{side\}-player \{player\} requiere --\{side\}-evaluator null'\))$",False),
    (r"(?m)^(\s*if ev=='null' and player not in )\(([^\n)]*)\)(:ap\.error\(f'--\{side\}-evaluator null requiere player [^'\n]*'\))$",True),
]
result=source
for pattern, fix_message in checks:
    regex=re.compile(pattern)
    matches=list(regex.finditer(result))
    if len(matches)!=1:
        raise SystemExit(f'ERROR: no se identificó exactamente una condición {pattern[:38]}; sin cambios')
    m=matches[0]
    players=[p.strip().strip("'\"") for p in m.group(2).split(',') if p.strip()]
    if 'tinyalpha' not in players: players.append('tinyalpha')
    entry='('+','.join(repr(p) for p in players)+')'
    suffix=m.group(3)
    if fix_message:
        suffix=":ap.error(f'--{side}-evaluator null requiere player " + ', '.join(players) + "')"
    result=result[:m.start()]+m.group(1)+entry+suffix+result[m.end():]
ast.parse(result)
if result==source:
    print('OK: tinyalpha ya registrado en ambas comprobaciones; sin cambios')
else:
    backup=path.with_name(path.name+'.before_v0.6.180.bak')
    if not backup.exists(): shutil.copy2(path,backup)
    path.write_text(result,encoding='utf-8')
    print('OK: actualizado',path,'; respaldo:',backup)
