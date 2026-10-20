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
#* test_cerebrum_player_incremental.py
#* Ejecuta pruebas de regresion para test cerebrum player incremental
#* v0.6.153
#=================================================================================================================*
from pathlib import Path
import numpy as np
import chess

from sargon_nnue.evaluators.cerebrum_v11 import CerebrumV11Evaluator, REQUIRED
from sargon_nnue.players.cerebrum_player import CerebrumPlayer
from sargon_nnue.evaluators.base import Evaluator


def _write_network(path: Path) -> None:
    # Deterministic non-zero quantized network; small values avoid overflow and
    # make incremental/full equivalence meaningful.
    rng = np.random.default_rng(12345)
    values = rng.integers(-2, 3, size=REQUIRED, dtype=np.int64)
    payload = "\n".join(str(int(x)) for x in values)
    path.write_text(
        "name=Cerebrum incremental test\n"
        "author=test\n"
        f"parameters={REQUIRED}\n"
        "wr=0.5\n"
        "mt=0.5\n" + payload + "\n",
        encoding="utf-8",
    )


def _assert_incremental_matches(ev: CerebrumV11Evaluator, board: chess.Board, move: chess.Move):
    parent = ev.evaluate_detailed(board)
    board.push(move)
    try:
        inc = ev.evaluate_incremental(board, parent)
        full = ev.evaluate_detailed(board)
        assert inc.score_cp == full.score_cp
        assert inc.score_white_float_cp == full.score_white_float_cp
        assert np.array_equal(inc.acc_white, full.acc_white)
        assert np.array_equal(inc.acc_black, full.acc_black)
        assert np.array_equal(inc.l1, full.l1)
        assert np.array_equal(inc.l2, full.l2)
        assert np.array_equal(inc.l3, full.l3)
    finally:
        board.pop()


def test_incremental_normal_capture_castle_ep_promotion(tmp_path: Path):
    fn = tmp_path / "network-q.txt"
    _write_network(fn)
    ev = CerebrumV11Evaluator(str(fn))

    b = chess.Board()
    _assert_incremental_matches(ev, b, chess.Move.from_uci("e2e4"))

    b = chess.Board("4k3/8/8/8/8/3p4/4P3/4K3 w - - 0 1")
    _assert_incremental_matches(ev, b, chess.Move.from_uci("e2d3"))

    b = chess.Board("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
    _assert_incremental_matches(ev, b, chess.Move.from_uci("e1g1"))

    b = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    _assert_incremental_matches(ev, b, chess.Move.from_uci("e5d6"))

    b = chess.Board("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
    _assert_incremental_matches(ev, b, chess.Move.from_uci("a7a8q"))


class MaterialEvaluator(Evaluator):
    name = "MATERIAL-TEST"
    VALUES = {chess.PAWN:100, chess.KNIGHT:320, chess.BISHOP:330, chess.ROOK:500, chess.QUEEN:900, chess.KING:0}
    def evaluate(self, board: chess.Board) -> int:
        s=0
        for p in board.piece_map().values():
            s += self.VALUES[p.piece_type] if p.color == chess.WHITE else -self.VALUES[p.piece_type]
        return s


def test_cerebrum_player_is_one_ply_and_evaluator_agnostic():
    board = chess.Board("4k3/8/8/8/8/3q4/4P3/4K3 w - - 0 1")
    player = CerebrumPlayer(MaterialEvaluator(), depth=9)
    choice = player.choose(board)
    assert choice.depth == 1
    assert choice.move == chess.Move.from_uci("e2e3") or choice.move in board.legal_moves
    assert choice.nodes == board.legal_moves.count()


def test_cerebrum_player_prefers_immediate_mate_over_static_eval():
    class Misleading(Evaluator):
        def evaluate(self, board: chess.Board) -> int:
            return -99999
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
    player = CerebrumPlayer(Misleading())
    choice = player.choose(board)
    board.push(choice.move)
    assert board.is_checkmate()
