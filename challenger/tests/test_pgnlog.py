from argparse import Namespace
from pathlib import Path

import chess
import chess.pgn

from challenger.pgnlog import append_game


def _read_games(path: Path):
    games = []
    with path.open(encoding="utf-8") as fh:
        while True:
            game = chess.pgn.read_game(fh)
            if game is None:
                break
            games.append(game)
    return games


def test_pgn_append_and_headers(tmp_path):
    path = tmp_path / "games.pgn"

    board1 = chess.Board()
    board1.push_uci("e2e4")
    board1.push_uci("e7e5")
    append_game(path, board1, chess.WHITE, "1-0", "Trainning run")

    board2 = chess.Board()
    board2.push_uci("d2d4")
    board2.push_uci("d7d5")
    append_game(path, board2, chess.BLACK, "0-1", "Night test")

    games = _read_games(path)
    assert len(games) == 2
    assert games[0].headers["White"] == "challenger"
    assert games[0].headers["Black"] == "nobody"
    assert games[0].headers["Event"] == "Trainning run"
    assert games[0].headers["Result"] == "1-0"
    assert games[1].headers["White"] == "nobody"
    assert games[1].headers["Black"] == "challenger"
    assert games[1].headers["Event"] == "Night test"
    assert games[1].headers["Result"] == "0-1"
    assert games[0].headers["Date"] != "????.??.??"
