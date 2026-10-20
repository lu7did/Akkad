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
#* test_npz.py
#* Ejecuta pruebas de regresion para test npz
#* v0.6.153
#=================================================================================================================*
import chess
from sargon_nnue.evaluators.npz import NpzEvaluator

def test_npz_roundtrip(tmp_path):
    p=tmp_path/'n.npz'; a=NpzEvaluator(str(p),require_weights=False); x=a.evaluate(chess.Board()); a.save()
    b=NpzEvaluator(str(p)); assert b.evaluate(chess.Board())==x
