"""Regression test for LC0 TinyGyal policy slots; run from Sargon-NNUE root.

Usage: python scripts/test_tinygyal_policy_special.py
"""
from __future__ import annotations
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
import chess
from sargon_nnue.evaluators.tinygyal import _policy_slot

cases=[
    ('8/P7/8/8/8/8/7p/4K2k w - - 0 1', 'a7a8n', (0,6,0)),
    ('8/P7/8/8/8/8/7p/4K2k w - - 0 1', 'a7a8r', (67,6,0)),
    ('8/P7/8/8/8/8/7p/4K2k w - - 0 1', 'a7a8b', (68,6,0)),
    ('8/P7/8/8/8/8/7p/4K2k w - - 0 1', 'a7a8q', (69,6,0)),
    ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1', 'e1c1', (43,0,4)),
    ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1', 'e1g1', (16,0,4)),
]
for fen,uci,expected in cases:
    b=chess.Board(fen);m=chess.Move.from_uci(uci)
    assert m in b.legal_moves, (fen,uci)
    actual=_policy_slot(b,m)
    assert actual==expected,(uci,actual,expected)
    print('PASS',uci,actual)
print(f'{len(cases)}/{len(cases)} mappings OK')
