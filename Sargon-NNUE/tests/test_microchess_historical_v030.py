"""Microchess v0.3 historical reconstruction regression tests."""
import chess
import pytest
from sargon_nnue.evaluators.microchess import (
    PieceTable,Janus,State,gnm,measure,Measurements,strategy_quarters,
    MicrochessEvaluator)
from sargon_nnue.evaluators import create_evaluator
from sargon_nnue.players import create_player


def test_original_square_encoding_and_slot_invariants():
    board=chess.Board();table=PieceTable(board)
    assert len(table.pieces)==32
    assert {p.square for p in table.pieces}==set(board.piece_map())
    assert {m.uci() for m in gnm(board,chess.WHITE,table=table)}=={m.uci() for m in board.legal_moves}
    assert sum(p.kind==chess.PAWN for p in table.pieces)==16

@pytest.mark.parametrize('uci', ['e2e4','g1f3','d2d4'])
def test_piece_table_reversible(uci):
    board=chess.Board();table=PieceTable(board)
    slots=[(p.color,p.kind,p.square) for p in table.pieces]
    move=chess.Move.from_uci(uci)
    table.push(move,board);board.push(move)
    assert {p.square for p in table.pieces if p.square!=0xff}==set(board.piece_map())
    board.pop();table.pop()
    assert slots==[(p.color,p.kind,p.square) for p in table.pieces]


def test_castling_and_en_passant_restoration():
    for fen,uci in [
      ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1','e1g1'),
      ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1','e5d6')]:
        board=chess.Board(fen);table=PieceTable(board)
        before=[(p.color,p.kind,p.square) for p in table.pieces]
        move=chess.Move.from_uci(uci)
        assert move in board.legal_moves
        table.push(move,board);board.push(move)
        assert {p.square for p in table.pieces if p.square!=0xff}==set(board.piece_map())
        board.pop();table.pop()
        assert before==[(p.color,p.kind,p.square) for p in table.pieces]


def test_janus_stages_and_strategy():
    board=chess.Board();j=Janus(board,exchange_branch=2)
    before=board.fen(); score=j.candidate(chess.Move.from_uci('e2e4'))
    assert isinstance(score,int)
    assert board.fen()==before
    assert not j.table._undos
    assert all(s in j.trace for s in (State.INITIAL,State.CANDIDATE,State.LEGALITY,
              State.CONTINUATION,State.RESPONSE,State.STRATEGY))
    assert strategy_quarters(Measurements(20),Measurements(28),Measurements(24),(0,0,0),(0,0,0))==-16


def test_player_cross_evaluator_and_score_contract():
    board=chess.Board()
    for kind in ('microchess','classic'):
        ev=create_evaluator(kind)
        p=create_player('microchess',ev,depth=1,qdepth=0,tmax_ms=20000)
        before=board.fen(); result=p.choose(board)
        assert result.move in board.legal_moves
        assert board.fen()==before
        assert isinstance(result.score_cp,int)
    ev=MicrochessEvaluator()
    assert ev.evaluate(chess.Board())==-ev.evaluate(chess.Board().mirror())


def test_players_sargon_compatible():
    for kind in ('sargon','sargon-plus'):
        ev=create_evaluator('microchess')
        p=create_player(kind,ev,depth=1,qdepth=0,tmax_ms=20000)
        assert p.choose(chess.Board()).move in chess.Board().legal_moves
