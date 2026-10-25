#!/usr/bin/env python3
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
#* apply_dmax_match.py
#* Parche mínimo verificable: incorpora --a-dmax/--b-dmax a MATCH.
#* v0.6.153
#=================================================================================================================*
"""Parche mínimo verificable: incorpora --a-dmax/--b-dmax a MATCH.
Uso: python apply_dmax_match.py ruta/al/sargon_match.py
"""
from pathlib import Path
import argparse
import ast
import difflib
import shutil
import sys


def patch(source):
    # No sustituir accidentalmente una versión completa del módulo.
    if "('dmax',None)" in source and "'depth','qdepth','dmax','tmax'" in source:
        print('OK: sargon_match.py ya acepta y transmite dmax; sin cambios.')
        return source, False
    old1="('depth',2),('qdepth',2),('tmax',15000)"
    new1="('depth',2),('qdepth',2),('dmax',None),('tmax',15000)"
    old2="'depth','qdepth','tmax'"
    new2="'depth','qdepth','dmax','tmax'"
    for name,needle in [('parser de los participantes',old1),('propagación al listener',old2)]:
        if source.count(needle) != 1:
            raise ValueError(f'{name}: patrón esperado no aparece exactamente una vez; no se modifica nada')
    changed=source.replace(old1,new1,1).replace(old2,new2,1)
    ast.parse(changed)
    return changed,True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archivo',type=Path,help='ruta a src/sargon_nnue/sargon_match.py')
    args=parser.parse_args()
    path=args.archivo
    data=path.read_bytes()
    # Preservar CRLF y bytes no alterados; identificadores buscados son ASCII.
    # latin-1 asegura roundtrip exacto byte por byte del origen.
    original=data.decode('latin-1')
    changed,edit=patch(original)
    if not edit:return
    backup=path.with_suffix(path.suffix+'.before_dmax.bak')
    if backup.exists():raise FileExistsError(f'Backup ya existe: {backup}; no se modifica nada')
    shutil.copy2(path,backup)
    path.write_bytes(changed.encode('latin-1'))
    print(f'OK: dmax añadido a ambos sides; backup: {backup}')
    print('Líneas modificadas:')
    for line in difflib.unified_diff(original.splitlines(),changed.splitlines(),fromfile='original',tofile='nuevo',lineterm=''):
        print(line)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        sys.exit(1)
