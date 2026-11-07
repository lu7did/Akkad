"""Tests: run with python -m pytest challenger/tests/test_monitor_v022.py."""
import chess
from challenger.monitor import PositionTracker, parse_endpoint


def test_endpoint():
    assert parse_endpoint("macia:6201") == ("macia", 6201)


def test_confirmed_moves_and_perspective():
    t = PositionTracker()
    assert t.feed("ucinewgame")
    assert t.feed("position startpos")
    assert t.feed("go wtime 15000 btime 15000")
    assert t.local_color == chess.WHITE
    t.feed("bestmove e2e4")
    assert t.board.fullmove_number == 1  # unconfirmed proposal never applied
    t.feed("position startpos moves e2e4 e7e5")
    assert t.last_local == "e4"
    assert t.last_remote == "e5"
    assert t.board.turn == chess.WHITE
    t.feed("info string monitor gameover 1-0")
    assert "finalizada" in t.message
    assert t.board.fullmove_number == 2
    t.feed("ucinewgame")
    assert t.board.fen() == chess.Board().fen()


def test_invalid_position_ignored():
    t = PositionTracker()
    t.feed("position startpos moves e2e4")
    fen = t.board.fen()
    t.feed("position startpos moves e2e5")
    assert t.board.fen() == fen
