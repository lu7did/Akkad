from argparse import Namespace

import chess
import pytest

from challenger.brain import RandomBrain, SargonBrain, make_brain


def test_sargon_brain_returns_legal_move():
    board = chess.Board()
    brain = SargonBrain(plies=2, qdepth=2, seed=1)
    result = brain.choose(board)
    assert result.move in board.legal_moves
    assert result.nodes and result.nodes > 0


def test_make_brain_defaults_to_sargon():
    args = Namespace(brain="sargon", plies=2, seed=1, timeout=120000, stockfish=None)
    brain = make_brain(args)
    assert brain.name == "sargon"
    brain.close()


def test_stockfish_requires_path():
    args = Namespace(brain="stockfish", plies=2, seed=1, timeout=120000, stockfish=None)
    with pytest.raises(ValueError):
        make_brain(args)


def test_random_brain_returns_legal_move():
    board = chess.Board()
    brain = RandomBrain(seed=1)
    result = brain.choose(board)
    assert result.move in board.legal_moves


def test_make_random_brain():
    args = Namespace(brain="random", plies=2, qdepth=2, seed=1, timeout=120000, stockfish=None)
    brain = make_brain(args)
    assert brain.name == "random"
    brain.close()
