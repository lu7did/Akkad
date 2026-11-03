import chess
import pytest

from challenger.cli import parser, main
from challenger.uci_client import TCPUCIClient

FEN = "r3k2r/ppp2ppp/2n5/3p4/8/2N5/PPPP1PPP/R3K2R b KQkq - 4 12"

def test_fen_option_case_insensitive_alias():
    assert parser().parse_args(["--FEN", FEN]).fen == FEN
    assert parser().parse_args(["--fen", FEN]).fen == FEN

def test_reject_invalid_fen_before_connect():
    with pytest.raises(SystemExit) as ex:
        main(["--FEN", "garbage"])
    assert ex.value.code == 2

def test_reject_illegal_board_before_connect():
    with pytest.raises(SystemExit) as ex:
        main(["--FEN", "8/8/8/8/8/8/8/4K3 w - - 0 1"])
    assert ex.value.code == 2

def test_uci_position_uses_fen_and_moves():
    client = TCPUCIClient("127.0.0.1", 6110)
    sent = []
    client.send = sent.append
    client.position(["e8g8", "e1g1"], FEN)
    assert sent == [f"position fen {FEN} moves e8g8 e1g1"]
    client.position([])
    assert sent[-1] == "position startpos"

def test_fen_position_turn_and_move_counters():
    board = chess.Board(FEN)
    assert board.turn == chess.BLACK
    assert board.fullmove_number == 12
    assert board.halfmove_clock == 4
