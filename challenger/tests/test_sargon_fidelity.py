import chess
import pytest
from challenger.sargon import SargonEngine


def test_no_quiescence_or_tt():
    engine = SargonEngine(plies=2)
    assert engine.qdepth == 0
    assert not hasattr(engine, "_tt")
    assert not hasattr(engine, "_quiescence")


def test_reject_modern_qdepth():
    with pytest.raises(ValueError):
        SargonEngine(plies=2, qdepth=2)


def test_deterministic_legal_and_unchanged_board():
    board = chess.Board()
    fen = board.fen()
    a = SargonEngine(plies=2).choose(board)
    b = SargonEngine(plies=2).choose(board)
    assert a.move == b.move
    assert a.score == b.score
    assert a.move in board.legal_moves
    assert board.fen() == fen


def test_mate_in_one():
    board = chess.Board("7k/6Q1/6K1/8/8/8/8/8 w - - 0 1")
    result = SargonEngine(plies=2).choose(board)
    board.push(result.move)
    assert board.is_checkmate()
