"""Registra tinyalpha de forma transaccional e idempotente. v0.6.176.
No reemplaza módulos completos; aborta sin cambios ante estructuras desconocidas.
"""
from __future__ import annotations
import argparse
import ast
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

REL = ['src/sargon_nnue/brains.py', 'src/sargon_nnue/cli_common.py',
       'src/sargon_nnue/factory.py', 'src/sargon_nnue/players/__init__.py']

def patch(root: Path):
    files={p:(root/p).read_text(encoding='utf-8') for p in REL}
    def sub(rel, pattern, replacement, *, flags=0):
        s=files[rel]
        m=list(re.finditer(pattern,s,flags))
        if len(m)!=1:raise RuntimeError(f'{rel}: esperaba 1 ancla ({pattern[:70]}), encontradas {len(m)}. No se modificó ningún archivo.')
        files[rel]=re.sub(pattern,replacement,s,count=1,flags=flags)
    b='src/sargon_nnue/brains.py'; f='src/sargon_nnue/factory.py'; c='src/sargon_nnue/cli_common.py'; p='src/sargon_nnue/players/__init__.py'
    if 'tinyalpha' not in re.search(r'^PLAYER_CHOICES\s*=.*$',files[b],re.M).group():
        sub(b,r'(^PLAYER_CHOICES\s*=\s*\([^\n]*)(\))',r"\1,'tinyalpha'\2",flags=re.M) # replace through direct below
    # Clean up potential doubled comma from unusual formatting.
    files[b]=files[b].replace(",,'tinyalpha'",",'tinyalpha'")
    if "player=='tinyalpha'" not in files[b]:
        sub(b,r"(^    if player=='picosargon' and ev!='null':)",
            "    if player=='tinyalpha' and ev!='null':raise ValueError('player tinyalpha requiere evaluator null')\n"
            "    if player=='tinyalpha' and not config.get('engine-path'):raise ValueError('player tinyalpha requiere engine-path')\n"
            "    if player=='tinyalpha' and not config.get('network'):raise ValueError('player tinyalpha requiere network')\n"+r'\1',flags=re.M)
    if "if player=='tinyalpha': allowed" not in files[b]:
        sub(b,r"(^        if player=='picosargon': allowed\|=.*$)",r'\1'+"\n        if player=='tinyalpha': allowed|={'network','az-simulations','az-cpuct','tmax'}",flags=re.M)
    if "'tinyalpha'" not in re.search(r"^    if player in \([^\n]+",files[b],re.M).group():
        sub(b,r"(^    if player in \([^\n]*)(\):)",r"\1,'tinyalpha'\2",flags=re.M)
    # Nullable evaluator validation: find conditional restricting null.
    for candidate in [r"(^    if player not in \([^\n]*)(\) and ev=='null':)"]:
        line=re.search(candidate,files[b],re.M)
        if line and "'tinyalpha'" not in line.group():sub(b,candidate,r"\1,'tinyalpha'\2",flags=re.M)
    if '"tinyalpha"' not in re.search(r'choices=\["random"[^\]]+\]',files[c]).group():
        sub(c,r'(choices=\["random"[^\]]*)(\])',r'\1, "tinyalpha"\2')
    if '"tinyalpha"' not in re.search(r'if player_kind in \{"stockfish", "random"[^}]+\}',files[f]).group():
        sub(f,r'(if player_kind in \{"stockfish", "random"[^}]+)(\}:)',r'\1, "tinyalpha"\2')
    if 'network=g("network", None)' not in files[f]:
        sub(f,r'(^        engine_path=g\("engine_path", None\),\s*$)',r'\1'+'\n        network=g("network", None),',flags=re.M)
        # Could have multiple engine_path occurrences; see note below
    if '"tinyalpha"' not in files[p] and 'if key == "tinyalpha"' not in files[p]:
        sub(p,r'(^    if key == "picosargon":)',
            '    if key == "tinyalpha":\n'
            '        from .tinyalpha_uci import TinyAlphaUCIPlayer\n'
            '        return TinyAlphaUCIPlayer(engine_path, network, simulations=az_simulations, cpuct=az_cpuct, tmax_ms=tmax_ms, timeout_ms=timeout_ms)\n'
            +r'\1',flags=re.M)
    if 'network: str | None = None' not in files[p]:
        sub(p,r'(engine_path: str \| None = None,)',r'\1 network: str | None = None,')
    for path,data in files.items():ast.parse(data,filename=path)
    return files

def install(root:Path, dry_run=False):
    for rel in REL:
        if not (root/rel).is_file():raise FileNotFoundError(root/rel)
    if not (root/'src/sargon_nnue/players/tinyalpha_uci.py').is_file():
        raise FileNotFoundError('Falta players/tinyalpha_uci.py: extraer primero v0.6.174')
    changed=patch(root)
    targets={r:t for r,t in changed.items() if t!=(root/r).read_text(encoding='utf-8')}
    print('Archivos a modificar:', *(targets or ['ninguno']),sep='\n  ')
    if dry_run:return
    for rel,new in targets.items():
        target=root/rel;backup=target.with_name(target.name+'.tinyalpha_v06176.bak')
        if not backup.exists():shutil.copy2(target,backup)
    written=[]
    try:
        for rel,new in targets.items():
            target=root/rel; temp=target.with_name(target.name+'.tinyalpha.tmp')
            temp.write_text(new,encoding='utf-8');os.replace(temp,target);written.append(rel)
    except Exception:
        for rel in written:shutil.copy2(root/(rel+'.tinyalpha_v06176.bak'),root/rel)
        raise
    # Static integration assertions avoid importing native-related optional deps.
    from importlib.util import spec_from_file_location, module_from_spec
    src=changed['src/sargon_nnue/brains.py']
    assert "'tinyalpha'" in re.search(r'^PLAYER_CHOICES\s*=.*$',src,re.M).group()
    assert "player=='tinyalpha'" in src
    print('Registro tinyalpha instalado. Python syntax: OK. Reejecutar es seguro.')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--dry-run',action='store_true');a=ap.parse_args()
    install(a.root.resolve(),a.dry_run)
if __name__=='__main__':
    try:main()
    except Exception as e:print('ERROR:',e,file=sys.stderr);sys.exit(1)
