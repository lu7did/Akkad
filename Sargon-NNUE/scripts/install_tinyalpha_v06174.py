"""Conservative idempotent registry integration in an existing Sargon-NNUE tree.
Will abort on unexpected code layout. Backs up every modified file to *.tinyalpha_before.
"""
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
src=root/'src/sargon_nnue'

def replace(path,old,new):
    t=path.read_text(encoding='utf-8')
    if new in t:return
    if old not in t:raise RuntimeError(f'Cannot find expected integration anchor in {path}: {old[:80]!r}')
    t=t.replace(old,new,1)
    backup=path.with_name(path.name+'.tinyalpha_before')
    if not backup.exists():backup.write_text(path.read_text(encoding='utf-8'),encoding='utf-8')
    path.write_text(t,encoding='utf-8')

def main():
 p=src/'players/__init__.py'
 replace(p,'    if key == "picosargon":','    if key == "tinyalpha":\n        from .tinyalpha_uci import TinyAlphaUCIPlayer\n        return TinyAlphaUCIPlayer(engine_path, network, simulations=az_simulations, cpuct=az_cpuct, tmax_ms=tmax_ms, timeout_ms=timeout_ms)\n    if key == "picosargon":')
 replace(p,'engine_path: str | None = None,', 'engine_path: str | None = None, network=None,')
 f=src/'factory.py'
 replace(f,'"picosargon", "external"}', '"picosargon", "external", "tinyalpha"}')
 replace(f,'player_kind in {"stockfish", "random", "lc0", "picosargon"}', 'player_kind in {"stockfish", "random", "lc0", "picosargon", "tinyalpha"}') if 'player_kind in {"stockfish", "random", "lc0", "picosargon"}' in f.read_text() else None
 replace(f,'        engine_path=g("engine_path", None),','        engine_path=g("engine_path", None),\n        network=g("network", None),')
 b=src/'brains.py'
 replace(b,"'doc','picosargon'","'doc','picosargon','tinyalpha'")
 replace(b,"'lc0','picosargon'):","'lc0','picosargon','tinyalpha'):")
 replace(b,"if player=='picosargon': allowed|={'qdepth','tmax'}","if player=='picosargon': allowed|={'qdepth','tmax'}\n        if player=='tinyalpha': allowed|={'network','az-simulations','az-cpuct','tmax'}")
 replace(b,"if player=='picosargon' and ev!='null':","if player=='tinyalpha' and ev!='null':raise ValueError('player tinyalpha requiere evaluator null')\n    if player=='tinyalpha' and not config.get('engine-path'):raise ValueError('player tinyalpha requiere engine-path')\n    if player=='tinyalpha' and not config.get('network'):raise ValueError('player tinyalpha requiere network')\n    if player=='picosargon' and ev!='null':")
 replace(b,"'random','lc0','picosargon','external') and ev=='null'","'random','lc0','picosargon','external','tinyalpha') and ev=='null'")
 c=src/'cli_common.py'
 replace(c,'"doc", "picosargon"','"doc", "picosargon", "tinyalpha"')
 print('tinyAlpha registry installed; existing sources backed up to *.tinyalpha_before')
if __name__=='__main__':
 try:main()
 except Exception as exc:print('INTEGRATION FAILED:',exc,file=sys.stderr);sys.exit(1)
