"""Microchess pair and the shared evaluator contract."""
import argparse
import chess
import pytest
from sargon_nnue.brains import validate, to_argv
from sargon_nnue.cli_common import add_engine_args
from sargon_nnue.factory import build_engine
from sargon_nnue.players import create_player
from sargon_nnue.evaluators import create_evaluator

@pytest.mark.parametrize('ev',['microchess','classic'])
def test_microchess_player_and_evaluator(ev):
    evaluator=create_evaluator(ev)
    player=create_player('microchess',evaluator,depth=1,qdepth=0,tmax_ms=10000)
    board=chess.Board();before=board.fen()
    choice=player.choose(board)
    assert choice.move in board.legal_moves
    assert choice.depth == 1
    assert board.fen()==before
    assert isinstance(choice.score_cp,int)
    assert choice.source == 'MICROCHESS'

def test_white_perspective_and_piece_squares():
    e=create_evaluator('microchess')
    board=chess.Board()
    assert isinstance(e.evaluate(board),int)
    assert e.evaluate(board)==-e.evaluate(board.mirror())

def test_brains_and_factory():
    for ev in ('microchess','classic'):
        cfg=validate({'player':'microchess','evaluator':ev,'depth':1,'qdepth':0})
        parser=argparse.ArgumentParser()
        add_engine_args(parser)
        args=parser.parse_args(to_argv(cfg))
        evaluator, player = build_engine(args)
        assert player.choose(chess.Board()).move in chess.Board().legal_moves

def test_external_picosargon_is_not_composable():
    with pytest.raises(ValueError):
        validate({'player':'picosargon','evaluator':'microchess','engine-path':'x'})


def test_janus_polynomial_and_gnm_contract():
    from sargon_nnue.evaluators.microchess import (
        Measurements, strategy_quarters, gnm, exchanges, MicrochessEvaluator
    )
    p = Measurements(20, 0, 0)
    w = Measurements(28, 0, 0)
    b = Measurements(24, 0, 0)
    assert strategy_quarters(p, w, b, (0, 0, 0), (0, 0, 0)) == -16
    board = chess.Board()
    assert set(gnm(board, chess.WHITE)) == set(board.legal_moves)
    assert exchanges(board, chess.WHITE) == ((0, 0, 0), (0, 0, 0))
    e = MicrochessEvaluator()
    before = board.fen()
    assert isinstance(e.evaluate_candidate(board, chess.Move.from_uci('e2e4')), int)
    assert board.fen() == before


@pytest.mark.parametrize('player_kind', ['sargon', 'sargon-plus'])
def test_other_python_players_accept_microchess_evaluator(player_kind):
    evaluator = create_evaluator('microchess')
    player = create_player(player_kind, evaluator, depth=1, qdepth=0, tmax_ms=3000)
    assert player.choose(chess.Board()).move in chess.Board().legal_moves
