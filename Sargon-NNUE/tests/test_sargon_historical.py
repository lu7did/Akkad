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
#* test_sargon_historical.py
#* Ejecuta pruebas de regresion para test sargon historical
#* v0.6.153
#=================================================================================================================*
import chess
from sargon_nnue.players import create_player
from sargon_nnue.players.sargon import SargonCore
from sargon_nnue.players.sargon_plus import SargonPlusPlayer
from sargon_nnue.players.sargon_historical import SargonHistoricalPlayer

class Material:
    name = 'CLASSIC'
    def evaluate(self, board):
        values = {chess.PAWN:100, chess.KNIGHT:320, chess.BISHOP:330,
                  chess.ROOK:500, chess.QUEEN:900, chess.KING:0}
        return sum(values[p.piece_type] * (1 if p.color == chess.WHITE else -1)
                   for p in board.piece_map().values())

def test_factory_and_plus_are_separate():
    e = Material()
    historical = create_player('sargon', e, depth=2, qdepth=3)
    modern = create_player('sargon-plus', e, depth=2, qdepth=3)
    assert isinstance(historical, SargonHistoricalPlayer)
    assert isinstance(modern, SargonPlusPlayer)
    assert type(modern).__mro__[1] is SargonCore
    assert historical.qdepth == 0 and not historical.iterative_deepening
    assert modern.qdepth == 3

def test_historical_legal_deterministic_and_board_unchanged():
    e = Material(); board = chess.Board(); before = board.fen()
    a = create_player('sargon', e, depth=2, seed=1)
    b = create_player('sargon', e, depth=2, seed=987)
    ma = a.choose(board); mb = b.choose(board)
    assert ma.move in board.legal_moves and ma.move == mb.move
    assert ma.depth == 2 and ma.nodes > 0 and board.fen() == before

def test_historical_never_uses_inherited_qsearch_tt_or_sort():
    e = Material()
    p = create_player('sargon', e, depth=1, qdepth=4)
    def should_not_run(*args, **kwargs):
        raise AssertionError('Modern SargonCore feature was used')
    p._quiescence = should_not_run
    p._move_order_score = should_not_run
    p._prepare_search = should_not_run
    choice = p.choose(chess.Board())
    assert choice.move in chess.Board().legal_moves
    assert p._tt == {}
