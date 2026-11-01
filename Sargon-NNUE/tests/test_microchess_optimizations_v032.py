"""Regression tests for derived occupancy, reference reuse and timers."""
import chess
from sargon_nnue.evaluators.microchess import PieceTable, Janus, measure
from sargon_nnue.players.microchess import MicrochessPlayer
from sargon_nnue.evaluators.microchess import MicrochessEvaluator


def check_table(board, table):
    for sq in chess.SQUARES:
        idx = table.occupant(sq)
        actual = board.piece_at(sq)
        if actual is None:
            assert idx is None, chess.square_name(sq)
        else:
            assert idx is not None, chess.square_name(sq)
            p = table.pieces[idx]
            assert (p.color, p.kind, p.square) == (actual.color, actual.piece_type, sq)


def test_reversible_index_castle_ep_promotion():
    for fen, uci in (
        (chess.STARTING_FEN, 'e2e4'),
        ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1', 'e1g1'),
        ('8/8/8/3pP3/8/8/8/K6k w - d6 0 1', 'e5d6'),
        ('7k/P7/8/8/8/8/8/K7 w - - 0 1', 'a7a8q'),
    ):
        board = chess.Board(fen)
        table = PieceTable(board)
        check_table(board, table)
        old = board.fen()
        move = chess.Move.from_uci(uci)
        assert move in board.legal_moves
        table.push(move, board)
        board.push(move)
        check_table(board, table)
        board.pop()
        table.pop()
        assert board.fen() == old
        check_table(board, table)


def test_reuse_reference_measurements_exact():
    board = chess.Board()
    table = PieceTable(board)
    move = chess.Move.from_uci('e2e4')
    from collections import Counter
    m0 = Counter()
    m1 = Counter()
    baseline = Janus(board, table=table, exchange_branch=2, metrics=m0).candidate(move)
    ref = measure(board, board.turn, table, m1)
    accelerated = Janus(board, table=table, exchange_branch=2, metrics=m1).candidate(move, previous=ref)
    assert accelerated == baseline
    assert m0['measure_calls'] == m1['measure_calls']
    assert m1['gnm_time_ms'] >= 0
    assert m1['tree_time_ms'] >= 0
    assert m1['measure_time_ms'] >= 0


def test_player_metrics_and_legal_move():
    board = chess.Board('4k3/8/8/8/8/8/4P3/4K3 w - - 0 1')
    player = MicrochessPlayer(MicrochessEvaluator(), depth=1, qdepth=0, tmax_ms=30000)
    choice = player.choose(board)
    assert choice.move in board.legal_moves
    metrics = player.last_metrics
    assert metrics['reference_cache_entries'] >= 1
    assert metrics['reference_cache_misses'] >= 1
    assert metrics['gnm_time_ms'] >= 0
    assert metrics['measure_time_ms'] >= 0
    assert metrics['tree_time_ms'] >= 0
