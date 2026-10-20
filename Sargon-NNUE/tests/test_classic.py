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
#* test_classic.py
#* Ejecuta pruebas de regresion para test classic
#* v0.6.153
#=================================================================================================================*
import chess
from sargon_nnue.evaluators.classic import ClassicEvaluator
from sargon_nnue.players.sargon import SargonPlayer

def test_classic_start_is_finite():
    assert isinstance(ClassicEvaluator().evaluate(chess.Board()), int)

def test_sargon_returns_legal_move():
    b=chess.Board(); c=SargonPlayer(ClassicEvaluator(),depth=1).choose(b)
    assert c.move in b.legal_moves
