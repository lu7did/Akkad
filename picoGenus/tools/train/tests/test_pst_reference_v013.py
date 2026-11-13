"""Regression: do not silently change the supplied example's behavior."""
import ast
import sys
from pathlib import Path
import numpy as np
import chess

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gen_pst_core as dut
from genPST import evaluate_fitness, evolve, build_dataset


def test_known_reference_evaluation():
    # Independently calculate material/structure expectation in starting position.
    p={'PAWN_VALUE':100,**{k:0 for k in dut.NAMES}}
    board=chess.Board()
    assert dut.evaluate(board,p)==0
    p['KNIGHT_VALUE']=500
    assert dut.evaluate(board,p)==0
    board.remove_piece_at(chess.B8)
    assert dut.evaluate(board,p)==500


def test_reference_unused_parameters_are_inert():
    board=chess.Board()
    p={'PAWN_VALUE':100,**{k:0 for k in dut.NAMES}}
    reference=dut.evaluate(board,p)
    for key in ('BACKWARD_PAWN_PENALTY','WEAK_SQUARE_PENALTY',
                'ROOK_CONNECTED','ROOK_BEHIND_PASSED_PAWN','KING_PRESSURE_MULT'):
        p[key]=63
    assert dut.evaluate(board,p)==reference


def test_reference_fitness_no_rmse():
    board=chess.Board()
    p={k:0 for k in dut.NAMES}
    chromosome=dut.encode_values([p[k] for k in dut.NAMES])
    selected=dut.choose_move(board,{'PAWN_VALUE':100,**p})
    fit,hits=evaluate_fitness(chromosome,[(board,selected)])
    assert (fit,hits)==(1,1)
    opposite=next(m for m in board.legal_moves if m!=selected)
    fit,hits=evaluate_fitness(chromosome,[(board,opposite)])
    assert (fit,hits)==(0,0)


def test_pst_evolution_reference(tmp_path):
    board=chess.Board()
    move=next(iter(board.legal_moves))
    out=evolve([(board,move)],population=4,generations=2,seed=3,on_progress=lambda msg:None)
    assert out['fitness']==out['correct']**2
    assert out['reference']=='entrenar_david_ga.py'


def test_nurse_shared_evaluator():
    board=chess.Board()
    p=[1]*len(dut.NAMES)
    assert dut.evaluate(board,p)==dut.evaluar_posicion_david(board,{'PAWN_VALUE':100,**dict(zip(dut.NAMES,p))})
