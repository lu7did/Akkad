#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* test_sargon_challenger_parity.py
#* Ejecuta pruebas de regresion para test sargon challenger parity
#* v0.6.153
#=================================================================================================================*
import chess

from sargon_nnue.evaluators.classic import ClassicEvaluator
from sargon_nnue.players.sargon import SargonPlayer


def test_classic_startpos_is_balanced():
    ev = ClassicEvaluator()
    assert ev.evaluate(chess.Board()) == 0


def test_sargon_has_challenger_qdepth_default():
    p = SargonPlayer(ClassicEvaluator(), depth=3, seed=0)
    assert p.qdepth == 2


def test_sargon_returns_legal_move_depth3():
    b = chess.Board()
    p = SargonPlayer(ClassicEvaluator(), depth=3, seed=0)
    choice = p.choose(b)
    assert choice.move in b.legal_moves
    assert choice.nodes > 0
