"""Nurse plugin adapter for the standalone picoBit BNN evaluator.

The implementation and its network format reside in picoBit/src/bnn.py.
"""
from __future__ import annotations
from pathlib import Path
import importlib.util
import sys


def _implementation():
    project_root = Path(__file__).resolve().parents[3]
    source = project_root / 'picoBit' / 'src' / 'bnn.py'
    if not source.is_file():
        raise FileNotFoundError(f'BNN picoBit no encontrado: {source}')
    name = '_akkad_picobit_bnn'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return sys.modules[name]


def make_bnn(network=None, **_kwargs):
    if not network:
        raise ValueError('BNN requiere evaluator.network (.keras)')
    return _implementation().BNNEvaluator(network)
