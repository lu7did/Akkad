from __future__ import annotations

from datetime import datetime
from pathlib import Path

import chess
import chess.pgn


def append_game(
    filename: str | Path,
    board: chess.Board,
    challenger_color: chess.Color,
    result: str,
    event: str = "Trainning run",
) -> None:
    """Append one completed game to a PGN file.

    ``board`` must contain the complete move stack for the game. The result is
    supplied explicitly so non-board terminations (for example timeout) are
    represented correctly too.
    """
    path = Path(filename).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    game = chess.pgn.Game.from_board(board)
    game.headers["Event"] = event
    game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
    game.headers["White"] = "challenger" if challenger_color == chess.WHITE else "nobody"
    game.headers["Black"] = "challenger" if challenger_color == chess.BLACK else "nobody"
    game.headers["Result"] = result

    exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
    text = game.accept(exporter)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(text.rstrip())
        fh.write("\n\n")
