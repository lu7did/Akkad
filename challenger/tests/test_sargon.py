import chess
from challenger.sargon import SargonEngine

def test_sargon_returns_legal_move():
    board=chess.Board()
    result=SargonEngine(plies=2, seed=1).choose(board)
    assert result.move in board.legal_moves
    assert result.nodes > 0

def test_sargon_takes_mate_in_one():
    board=chess.Board("7k/6Q1/6K1/8/8/8/8/8 w - - 0 1")
    result=SargonEngine(plies=2, seed=1).choose(board)
    board.push(result.move)
    assert board.is_checkmate()


def test_sargon_honors_expired_deadline():
    import time
    import pytest
    from challenger.sargon import SearchTimeout

    board = chess.Board()
    with pytest.raises(SearchTimeout):
        SargonEngine(plies=2, seed=1).choose(board, deadline=time.monotonic() - 0.001)
