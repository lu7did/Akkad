import chess
from sargon_nnue.evaluators.grumpy import GrumpyEvaluator
from sargon_nnue.players.doc import DocPlayer

def test_grumpy():
    evaluator=GrumpyEvaluator()
    b=chess.Board()
    assert isinstance(evaluator.evaluate(b), int)
    assert evaluator.evaluate(b)==-evaluator.evaluate(b.mirror())

def test_doc():
    b=chess.Board()
    p=DocPlayer(GrumpyEvaluator(),depth=2,qdepth=2,tmax_ms=1500)
    result=p.choose(b)
    assert result.move in b.legal_moves
    assert b.fen()==chess.Board().fen()
