# UCI Screen Observer

Passive graphical observer for chess UCI exchanges **printed to a GNU Screen terminal**. Shows the current confirmed position on a Tkinter board (white at bottom). Uses `python-chess` to validate FEN and every move before changing the board.

## Requirements

- Linux with `screen`, Python 3.9+ and Tkinter (`sudo apt install screen python3-tk` on Debian/Ubuntu)
- `python3 -m pip install python-chess`
- Same user/account as the Screen session, or permission to issue Screen commands.

## Usage

```sh
screen -ls
python3 uci_screen_gui.py mysession
# Or use a full ID, e.g. 12345.mysession
python3 uci_screen_gui.py 12345.mysession --poll 0.25 --flush 1
```

Run the observer **after the Screen session exists**, and while the UCI transcript is being printed. On startup it enables Screen logging to a temporary file and polls that file. Closing the GUI disables that logging. **It changes the logging configuration of the specified Screen session**, so do not run alongside an existing Screen logger unless you are willing to replace it. Logging only captures output produced after the observer starts.

## Semantics

- `position startpos moves e2e4 e7e5 ...` and `position fen <six FEN fields> moves ...`: construct a *temporary* board and validate every move sequentially; commit only if the full position is legal.
- `bestmove e2e4`: check whether the proposed move is legal in the last confirmed board. **Do not apply it:** UCI `bestmove` is a suggestion; the GUI changes only on a new `position` command.
- `uci`, `isready`, `readyok`, `go`, `info`, `ucinewgame`, etc.: display protocol activity. `ucinewgame` does not itself reset the chessboard.
- Accept raw printed commands and a few common directional markers, including `⬅️ position ...`.
- Invalid positions are logged and ignored, retaining the last known valid position.

## Important limitations

1. **Screen's logging captures the terminal's visible output, not a hidden bidirectional UCI TCP/pipe stream.** If the application does not print incoming `position ...` commands, there is not enough information to reconstruct its chess state. For exact two-way monitoring, instrument the bridge or use a proxy between UCI peers that logs both directions.
2. UCI by itself does not include a complete move history in `bestmove`. The authoritative messages are `position ...`.
3. If several games or engines share the same Screen window, this implementation will track whichever valid `position` message was most recently observed. It does not implement per-connection demultiplexing.
4. `screen` logfile flushes periodically, so GUI updates are delayed by the configured flush interval.
5. This script is designed for standard chess, not Chess960 or chess variants.
6. This code was syntax-checked; a live GNU Screen/GUI integration test still requires a local Linux environment.
