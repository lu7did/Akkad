"""Nurse's 'bnn' evaluator: Bullet Genesis BULBNN01 binary weights.

Legacy picoBit model readers remain in picoBit/src/bnn.py and are untouched,
but are no longer used for the Nurse evaluator ID 'bnn'.
"""
from __future__ import annotations

from . import bullet_bnn


def _implementation():
    """Compatibility entry point used by Nurse's BNN registry adapter."""
    return bullet_bnn


def make_bnn(network=None, **_kwargs):
    if not network:
        raise ValueError('BNN requiere evaluator.network (Bullet BULBNN01 .bnn)')
    return bullet_bnn.BNNEvaluator(network)
