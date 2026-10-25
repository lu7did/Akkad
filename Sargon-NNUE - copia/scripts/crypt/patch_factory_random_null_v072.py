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
#* patch_factory_random_null_v072.py
#* Apply narrow RANDOM/NULL fix to user's existing factory.py; leave other code untouched.
#* v0.6.153
#=================================================================================================================*
"""Apply narrow RANDOM/NULL fix to user's existing factory.py; leave other code untouched."""
from pathlib import Path
import sys
p = Path(__file__).resolve().parents[1] / 'src' / 'sargon_nnue' / 'factory.py'
if not p.is_file():
    raise SystemExit(f'ERROR: factory.py no encontrado: {p}')
s = p.read_text(encoding='utf-8')
old = 'if evaluator_kind == "null":\n                raise PlayerError("evaluator=null sólo es válido con player=stockfish")'
new = 'if evaluator_kind == "null" and player_kind != "random":\n                raise PlayerError("evaluator=null sólo es válido con player=stockfish o random")'
if new in s:
    print('factory.py: corrección ya instalada')
elif old not in s:
    raise SystemExit('ERROR: factory.py difiere de la versión conocida; no se modificó. Revisar su validación evaluator=null manualmente.')
else:
    backup=p.with_suffix('.py.pre072.bak')
    if backup.exists():
        raise SystemExit(f'ERROR: backup ya existe: {backup}; no se modificó nada.')
    backup.write_text(s, encoding='utf-8')
    p.write_text(s.replace(old,new,1), encoding='utf-8')
    print(f'factory.py actualizado; respaldo: {backup}')
