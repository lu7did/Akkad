"""picoKeras C++ model via UCI stdio (TCP is served by sargon_listen)."""
from __future__ import annotations

import queue
import time
from pathlib import Path

import chess

from .base import PlayerError
from .uci_external import ExternalUCIPlayer
from ..types import MoveChoice


class PicoKerasUCIPlayer(ExternalUCIPlayer):
    name = "PICOKERAS"

    def __init__(self, executable, network, *, timeout_ms=30000, tmax_ms=15000):
        exe = Path(executable).expanduser().resolve() if executable else None
        weights = Path(network).expanduser().resolve() if network else None
        if not exe or not exe.is_file():
            raise PlayerError(f"picoKeras: engine-path inexistente: {exe}")
        if not weights or not weights.is_dir():
            raise PlayerError(f"picoKeras: network inexistente: {weights}")
        if weights.suffix.lower() != '.tf' or not (weights / "saved_model.pb").is_file():
            raise PlayerError(f"picoKeras Desktop: network debe ser un directorio SavedModel .tf con saved_model.pb: {weights}")
        self.tmax_ms = int(tmax_ms)
        if self.tmax_ms < 0 or int(timeout_ms) < 1:
            raise PlayerError("picoKeras: tmax>=0 y timeout>=1 requeridos")
        # picoKeras UCI does not accept setoption for its network: it must be on argv.
        super().__init__(
            [str(exe), '--network', str(weights), '--stdio'],
            movetime_ms=max(self.tmax_ms, 1),
            timeout_ms=max(int(timeout_ms), self.tmax_ms + 10000),
            label=self.name,
        )

    def choose(self, board: chess.Board) -> MoveChoice:
        started = time.monotonic()
        # Search uses a one-ply evaluation; transmit the current position as FEN.
        self._send('position fen ' + board.fen())
        self._send('go')  # native engine is searchless 1ply; ignores go movetime/nodes
        best = None
        nodes = 0
        depth = 0
        deadline = started + self.timeout_ms / 1000
        while time.monotonic() < deadline:
            try:
                line = self.q.get(timeout=max(0.001, deadline - time.monotonic()))
            except queue.Empty:
                break
            if line is None:
                raise PlayerError('picoKeras: proceso UCI finalizó inesperadamente')
            if line.startswith('info '):
                tokens = line.split()
                for key in ('nodes', 'depth'):
                    if key in tokens:
                        try:
                            value = int(tokens[tokens.index(key) + 1])
                            if key == 'nodes':
                                nodes = value
                            else:
                                depth = value
                        except (ValueError, IndexError):
                            pass
            if line.startswith('bestmove '):
                parts = line.split()
                best = parts[1] if len(parts) > 1 else '(none)'
                break
        if best is None:
            raise PlayerError('picoKeras: timeout esperando bestmove')
        move = None if best in ('0000', '(none)') else chess.Move.from_uci(best)
        if move is not None and move not in board.legal_moves:
            raise PlayerError(f'picoKeras: movimiento ilegal: {best}')
        # Native info exposes eval_rival (not UCI score cp); avoid inventing cp.
        return MoveChoice(move, 0, depth, nodes, (time.monotonic() - started) * 1000, self.name)
