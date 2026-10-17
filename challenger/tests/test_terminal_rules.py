import chess

from challenger.game import ChallengerRunner
from challenger.sargon import SargonEngine


def _repeat_knights(board: chess.Board, cycles: int) -> None:
    for _ in range(cycles):
        for uci in ("g1f3", "g8f6", "f3g1", "f6g8"):
            board.push_uci(uci)


def test_checkmate_is_terminal():
    board = chess.Board()
    for san in ("f3", "e5", "g4", "Qh4#"):
        board.push_san(san)
    assert board.is_checkmate()
    assert board.is_game_over(claim_draw=True)
    assert SargonEngine(2)._static(board, chess.WHITE) == -1.0


def test_stalemate_is_terminal_draw():
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert board.is_stalemate()
    assert board.is_game_over(claim_draw=True)
    assert SargonEngine(2)._static(board, chess.WHITE) == 0.0


def test_insufficient_material_is_terminal_draw():
    board = chess.Board("8/8/8/8/8/8/7k/K7 w - - 0 1")
    assert board.is_insufficient_material()
    assert board.is_game_over(claim_draw=True)


def test_seventyfive_moves_is_automatic_draw():
    board = chess.Board("8/8/8/8/8/8/R6k/K7 w - - 150 76")
    assert board.is_seventyfive_moves()
    assert board.is_game_over(claim_draw=False)


def test_fivefold_repetition_is_automatic_draw():
    board = chess.Board()
    _repeat_knights(board, 4)
    assert board.is_fivefold_repetition()
    assert board.is_game_over(claim_draw=False)


def test_threefold_repetition_is_claimed_by_challenger_controller():
    board = chess.Board()
    _repeat_knights(board, 2)
    assert board.can_claim_threefold_repetition()
    assert not board.is_game_over(claim_draw=False)
    assert board.is_game_over(claim_draw=True)


def test_fifty_move_rule_is_claimed_by_challenger_controller():
    board = chess.Board("8/8/8/8/8/8/R6k/K7 w - - 100 51")
    assert board.can_claim_fifty_moves()
    assert not board.is_game_over(claim_draw=False)
    assert board.is_game_over(claim_draw=True)


def test_timeout_is_loss_even_if_winner_has_insufficient_material():
    board = chess.Board("8/8/8/8/8/8/7k/K7 w - - 0 1")
    result = ChallengerRunner._result_by_timeout(board, True, chess.WHITE)
    assert result.outcome == "win"
    assert result.token == "1-0"
    assert result.reason == "TIMEOUT"


def test_timeout_is_win_if_nominal_winner_has_mating_material():
    board = chess.Board("8/8/8/8/8/8/R6k/K7 w - - 0 1")
    result = ChallengerRunner._result_by_timeout(board, True, chess.WHITE)
    assert result.outcome == "win"
    assert result.token == "1-0"
    assert result.reason == "TIMEOUT"
