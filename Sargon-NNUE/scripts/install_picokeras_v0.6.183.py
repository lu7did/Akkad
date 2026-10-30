"""Instala v0.6.183, verificando que el brain picoKeras pase las rutas de validación compartidas."""
from pathlib import Path
import subprocess
import sys
import os
import json

ROOT = Path(__file__).resolve().parent.parent
PATCH = ROOT / 'scripts' / 'apply_picokeras_integration_v0.6.182.py'

print('[picoKeras v0.6.183] Instalando integración...', flush=True)
run = subprocess.run([sys.executable, str(PATCH)], cwd=str(ROOT))
if run.returncode:
    raise SystemExit(f'ERROR: el aplicador falló ({run.returncode}); no se declara instalada la integración')

sys.path.insert(0, str(ROOT / 'src'))
try:
    from sargon_nnue import brains
    from sargon_nnue.factory import build_engine
    from sargon_nnue.players import create_player
    from sargon_nnue.cli_common import add_engine_args
    from sargon_nnue import sargon_match
    from sargon_nnue import sargon_benchmark
    from sargon_nnue import sargon_rally
    from sargon_nnue import sargon_listen
    import argparse
    for name in ('picoKeras','picokeras'):
        cfg = {'player':name,'evaluator':'null', 'engine-path':'../x86/picoKeras/build/Release/picoKeras.exe', 'network':'../data/runs/keras/small.int8.tflite','nodes':1}
        if brains.validate(cfg)['player'] != name:
            raise AssertionError(f'brains.validate rechazó {name}')
        brains.engine_parser().parse_args(brains.to_argv(cfg))
        p=argparse.ArgumentParser()
        add_engine_args(p, prefix='a_')
        p.parse_args(['--a-player',name,'--a-evaluator','null'])
    for f in ('factory.py','players/__init__.py','sargon_match.py'):
        target=ROOT/'src'/'sargon_nnue'/f
        if 'picokeras' not in target.read_text(encoding='utf-8').lower():
            raise AssertionError(f'Falta picokeras en {f}')
    print('[picoKeras v0.6.183] PASS: validación de brains, argparse, factory, match y módulos de listen/rally/benchmark importables.')
except Exception as exc:
    raise SystemExit(f'[picoKeras v0.6.183] FALLÓ LA VERIFICACIÓN: {type(exc).__name__}: {exc}')
