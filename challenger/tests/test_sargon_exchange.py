"""Regression tests for static single-square exchange evaluation."""
import chess
from challenger.sargon import SargonEngine


def test_unprotected_queen_loss():
    board = chess.Board("4k3/8/8/4q3/4R3/8/8/4K3 w - - 0 1")
    engine = SargonEngine(plies=1)
    assert engine._exchange_risk(board, chess.BLACK) >= 9.0
    assert board.fen() == "4k3/8/8/4q3/4R3/8/8/4K3 w - - 0 1"


def test_defended_pawn_exchange_not_full_piece_loss():
    board = chess.Board("4k3/8/3p4/4p3/3P4/8/8/4K3 w - - 0 1")
    engine = SargonEngine(plies=1)
    risk = engine._exchange_risk(board, chess.BLACK)
    assert risk >= 0.0
    assert board.fen() == "4k3/8/3p4/4p3/3P4/8/8/4K3 w - - 0 1"


def test_no_quiescence_or_tt():
    engine = SargonEngine(plies=2)
    assert engine.qdepth == 0
    assert not hasattr(engine, "_quiescence")
    assert not hasattr(engine, "_tt")


def test_exchange_has_no_side_effects():
    board = chess.Board()
    engine = SargonEngine(plies=1)
    before = board.fen()
    engine._exchange_risk(board, chess.WHITE)
    engine._exchange_risk(board, chess.BLACK)
    assert board.fen() == before
