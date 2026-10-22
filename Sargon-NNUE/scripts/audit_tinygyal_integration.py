#!/usr/bin/env python3
"""Read-only audit of TinyGyal registration across shared Sargon entry points."""
from pathlib import Path
import ast
import sys

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'src'/'sargon_nnue'
CHECKS={
 'evaluators/__init__.py': ('tinygyal', 'TinyGyalEvaluator', 'create_evaluator'),
 'factory.py': ('tinygyal', 'build_engine', 'alphazero'),
 'cli_common.py': ('tinygyal', 'lc0-backend', 'lc0-history'),
 'brains.py': ('tinygyal', 'EVALUATOR_CHOICES', 'ENGINE_KEYS'),
 'evaluators/tinygyal.py': ('TinyGyalEvaluator', 'evaluate_pv', 'TinyGyalTorch'),
 'evaluators/tinygyal_core.py': ('TinyGyalTorch',),
}
errors=[]
for rel, tokens in CHECKS.items():
 p=SRC/rel
 if not p.is_file(): errors.append(f'MISSING {p}');continue
 s=p.read_text(encoding='utf-8-sig')
 try:ast.parse(s,filename=str(p))
 except SyntaxError as exc: errors.append(f'SYNTAX {rel}: {exc}');continue
 absent=[t for t in tokens if t not in s]
 if absent: errors.append(f'REGISTRY {rel}: {absent}')
 else: print(f'PASS {rel}')
# Each program consumes common factory/brain/CLI functions; audit point-of-entry wiring.
for rel in ('sargon_match.py','sargon_benchmark.py','sargon_rally.py','sargon_listen.py','sargon_stdin.py'):
 p=SRC/rel
 if p.exists():
  s=p.read_text(encoding='utf-8-sig')
  print(('PASS' if any(t in s for t in ('brains','factory','cli_common','create_player','make_player','build_player')) else 'REVIEW')+' entry '+rel)
 else:print('NOT PRESENT entry '+rel)
print('AUDIT:', 'FAIL' if errors else 'PASS')
for error in errors:print(error,file=sys.stderr)
sys.exit(bool(errors))
