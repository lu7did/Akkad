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
#* test_stockfish_evaluator.py
#* Ejecuta pruebas de regresion para test stockfish evaluator
#* v0.6.153
#=================================================================================================================*
import chess

from sargon_nnue.evaluators.stockfish import StockfishEvaluator
from sargon_nnue.types import MATE_CP


def test_parse_final_evaluation_white_cp():
    lines = [
        "NNUE evaluation        +0.44 (white side)",
        "Final evaluation      -1.23 (white side) [with scaled NNUE, ...]",
        "readyok",
    ]
    assert StockfishEvaluator.parse_final_evaluation(lines) == -123


def test_parse_search_cp_normalizes_side_to_move():
    lines = ["info depth 1 score cp 37 nodes 12", "bestmove e7e5"]
    assert StockfishEvaluator.parse_search_score(lines, chess.WHITE) == 37
    assert StockfishEvaluator.parse_search_score(lines, chess.BLACK) == -37


def test_parse_search_mate_normalizes_side_to_move():
    lines = ["info depth 1 score mate 2 nodes 12", "bestmove h5f7"]
    assert StockfishEvaluator.parse_search_score(lines, chess.WHITE) == MATE_CP
    assert StockfishEvaluator.parse_search_score(lines, chess.BLACK) == -MATE_CP


def test_parse_final_evaluation_without_colon_from_real_stockfish_output():
    lines = [
        "NNUE evaluation          +104 (side to move, internal units)",
        "NNUE evaluation        +0.37 (white side)",
        "Final evaluation      +0.46 (white side) [with scaled NNUE, ...]",
        "",
        "readyok",
    ]
    assert StockfishEvaluator.parse_final_evaluation(lines) == 46


def test_parse_final_evaluation_with_colon_remains_supported():
    lines = ["Final evaluation: -0.81 (white side)", "readyok"]
    assert StockfishEvaluator.parse_final_evaluation(lines) == -81
