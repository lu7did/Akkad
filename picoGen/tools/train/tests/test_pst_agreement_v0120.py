"""Unit/regression tests for diagnostic-only one-ply agreement, no Stockfish."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
try:
    import chess
except ImportError:
    chess=types.ModuleType('chess')
    chess.__path__=[]
    for i,k in enumerate('ABCDEFGH'):
        for j in range(1,9):setattr(chess,f'{k}{j}',(j-1)*8+i)
    chess.PAWN=1; chess.KNIGHT=2; chess.BISHOP=3; chess.ROOK=4; chess.QUEEN=5
    chess.Board=lambda fen:fen
    chess.WHITE=True
    chess.Move=types.SimpleNamespace(from_uci=lambda s:s)
    sys.modules['chess']=chess
    sys.modules['chess.engine']=types.ModuleType('chess.engine')

import genPST as pst

class Board:
    def __init__(self, turn, values):
        self.turn=turn
        self.values=values
        self.legal_moves=list(values)
        self.active=None
    def push(self, move):self.active=move
    def pop(self):self.active=None

class Tests(unittest.TestCase):
    def test_agreement_and_perspective(self):
        white=Board(True,{'a':10.,'b':7.})
        black=Board(False,{'a':10.,'b':7.})
        with patch.object(pst,'evaluate',side_effect=lambda board, params:board.values[board.active]):
            result=pst.move_agreement([white,black,white,white],['a','b',None,'missing'],{},chess)
        self.assertEqual(result['move_agreement_correct'],2)
        self.assertEqual(result['move_agreement_total'],2)
        self.assertEqual(result['move_agreement_skipped'],2)
        self.assertEqual(result['move_agreement_pct'],100.0)
        self.assertIsNone(white.active)
        self.assertIsNone(black.active)

    def test_metric_does_not_change_fitness_or_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=str(Path(tmp)/'weights.json')
            samples=[('fen1',20.,'a'),('fen2',-10.,'b')]
            with patch.object(pst,'evaluate',return_value=4.),patch.object(pst,'move_agreement',return_value={
                 'move_agreement_correct':1,'move_agreement_total':2,
                 'move_agreement_skipped':0,'move_agreement_pct':50.0}):
                loss=pst.train(samples,out,3,1,7)
            snap=json.loads(Path(tmp,'weights.gen00001.json').read_text(encoding='utf-8'))
            self.assertEqual(snap['diagnostics']['move_agreement_pct'],50.0)
            self.assertAlmostEqual(loss,((4.-20.)**2+(4.+10.)**2)/2)
            self.assertEqual(sum(i['best'] for i in snap['individuals']),1)
            self.assertTrue(Path(tmp,'PST_best.json').exists())

    def test_dataset_hash_keeps_checkpoint_compatibility(self):
        self.assertEqual(pst.signature([('x',1.)]),pst.signature([('x',1.,'e2e4')]))

if __name__=='__main__':unittest.main()
