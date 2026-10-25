#!/usr/bin/env python3
"""Patch MINIMO de validacion null en sargon_match.py; idempotente y con backup."""
from __future__ import annotations
import argparse
import ast
from pathlib import Path
import re
import shutil

REQUIRES = "('stockfish', 'lc0', 'picosargon', 'tinyalpha')"
ALLOWS = "('stockfish', 'lc0', 'random', 'picosargon', 'tinyalpha')"


def patch(source: str) -> tuple[str, int]:
    # Solo las dos guardas de validacion en la funcion principal de MATCH.
    # Preserva el resto de sargon_match.py y los parametros existentes.
    rule1 = re.compile(r"(?m)^(\s*if player in )\(([^\n)]*)\)( and ev not in \('null',None\):ap\.error\(f'--\{side\}-player \{player\} requiere --\{side\}-evaluator null'\))$")
    rule2 = re.compile(r"(?m)^(\s*if ev=='null' and player not in )\(([^\n)]*)\)(:ap\.error\(f'--\{side\}-evaluator null requiere player [^'\n]*'\))$")
    n1 = len(rule1.findall(source)); n2 = len(rule2.findall(source))
    if n1 != 1 or n2 != 1:
        raise RuntimeError(f'Validadores esperados no identificados (requiere={n1}, permite={n2}). No se cambia nada.')
    out=rule1.sub(lambda m: m.group(1)+REQUIRES+m.group(3),source)
    out=rule2.sub(lambda m: m.group(1)+ALLOWS+":ap.error(f'--{side}-evaluator null requiere player stockfish, lc0, random, picosargon o tinyalpha')",out)
    ast.parse(out)
    return out,2


def main() -> None:
    parser=argparse.ArgumentParser(description='Registrar jugador tinyalpha en validaciones null de MATCH')
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--check', action='store_true',help='Auditar sin modificar')
    args=parser.parse_args()
    path=args.root/'src/sargon_nnue/sargon_match.py'
    if not path.exists():parser.error(f'No existe {path}')
    original=path.read_text(encoding='utf-8-sig')
    try: updated,_=patch(original)
    except RuntimeError as exc: parser.error(str(exc))
    if original==updated:
        print('OK: MATCH ya admite null con stockfish, lc0, random, picosargon y tinyalpha. Sin cambios.')
        return
    print('Correccion propuesta: validacion --a-evaluator/--b-evaluator null y obligatoriedad para player interno.')
    if args.check: print('CHECK OK. Sin cambios.');return
    backup=path.with_name(path.name+'.before_v0.6.179.bak')
    if not backup.exists():shutil.copy2(path,backup)
    path.write_text(updated,encoding='utf-8')
    print('OK:',path)
    print('Backup:',backup)
    print('Prueba sugerida: ejecutar run_match.ps1 con tinyalpha/null en lado A y en lado B.')

if __name__=='__main__': main()
