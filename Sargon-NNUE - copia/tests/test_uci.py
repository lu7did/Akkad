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
#* test_uci.py
#* Ejecuta pruebas de regresion para test uci
#* v0.6.153
#=================================================================================================================*
import io
from sargon_nnue.uci import UCISession
from sargon_nnue.evaluators.classic import ClassicEvaluator
from sargon_nnue.players.sargon import SargonPlayer

def test_uci_handshake_and_move():
    inp=io.StringIO('uci\nisready\nposition startpos\ngo\nquit\n'); out=io.StringIO()
    UCISession(SargonPlayer(ClassicEvaluator(),1),inp,out).loop(); text=out.getvalue()
    assert 'uciok' in text and 'readyok' in text and 'bestmove ' in text
