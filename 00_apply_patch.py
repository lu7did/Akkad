#!/usr/bin/env python3
"""Complete the MCTSE v0.1.38 patch without rewriting unrelated config.py.
Run from the root of akkad after unpacking the patch ZIP.
Idempotent; fails closed if the expected current config block has changed.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
TARGET = ROOT/'nurse/src/nurse/config.py'
BEFORE = '''        if name == 'mctsp':
            if not isinstance(network, str) or not network.strip():
                raise ValueError('MCTSP/MCTSE requiere evaluator.network con checkpoint .pt')
            if Path(network).suffix.lower() != '.pt':
                raise ValueError('MCTSE requiere checkpoint .pt (780x16, policy from_to, value tanh)')
'''
AFTER = '''        if name == 'mctsp':
            if not isinstance(network, str) or not network.strip():
                raise ValueError('MCTSP/MCTSE requiere evaluator.network con modelo .bin PANNI8 o .pt INT8')
            if Path(network).suffix.lower() not in ('.bin', '.pt'):
                raise ValueError('MCTSE requiere .bin PANNI8 o .pt INT8 (780x16, policy from_to, value tanh)')
'''

def main():
    if not TARGET.is_file():
        raise SystemExit(f'No existe {TARGET}. Extraer el ZIP desde la raíz de akkad.')
    text = TARGET.read_text(encoding='utf-8')
    if text.count(AFTER) == 1:
        print('✅ config.py ya admite PANNI8: sin cambios')
        return
    if text.count(BEFORE) != 1:
        raise SystemExit('ERROR: el bloque MCTSP de config.py no coincide con la base verificada; no se modificó el archivo')
    old = TARGET.with_suffix('.py.pre_mctse_v0138.bak')
    if not old.exists(): old.write_text(text, encoding='utf-8')
    TARGET.write_text(text.replace(BEFORE, AFTER, 1), encoding='utf-8')
    import py_compile
    py_compile.compile(str(TARGET), doraise=True)
    print(f'✅ MCTSE acepta .bin PANNI8 y .pt INT8 en {TARGET}')

if __name__ == '__main__':
    main()
