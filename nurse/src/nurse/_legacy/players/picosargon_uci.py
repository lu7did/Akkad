# Sargon-NNUE v0.6.164 - monolithic picoSargon host UCI player
from __future__ import annotations
import sys
import time
from pathlib import Path
import chess
from .uci_external import ExternalUCIPlayer
from .base import PlayerError
from ..types import MoveChoice

class PicoSargonUCIPlayer(ExternalUCIPlayer):
    name = "PICOSARGON"

    def __init__(self, executable: str, *, weights_path: str | None = None, depth=4, qdepth=2, tmax_ms=15000, timeout_ms=30000):
        executable = str(Path(executable).expanduser().resolve())
        if not Path(executable).is_file():
            raise PlayerError(f"picoSargon UCI no existe: {executable}")
        self.depth = int(depth)
        self.qdepth = int(qdepth)
        self.tmax_ms = int(tmax_ms)
        if self.depth < 1 or self.qdepth < 0 or self.tmax_ms < 0:
            raise PlayerError("picosargon: depth>=1, qdepth>=0, tmax>=0 requeridos")
        # The x86 UCI engine loads the Grumpy binary from argv[1].
        # --network / brains["network"] overrides the deployment default.
        # Without an explicit path, use the model distributed with picoSargon,
        # never a fixed path inside Sargon-NNUE.
        weights = (Path(weights_path).expanduser().resolve()
                   if weights_path else Path(executable).parent.parent / "assets" / "grumpy.bin")
        if not weights.is_file():
            raise PlayerError(f"picoSargon: pesos Grumpy inexistentes: {weights} "
                              f"(defina 'network' en brains.json)")
        with weights.open("rb") as f:
            header = f.read(12)
            f.seek(0, 2)
            length = f.tell()
        if length != 1304 or header[:8] != b"GRMP0001" or header[8:12] != b"\x69\x00\x00\x00":
            raise PlayerError(f"picoSargon: formato Grumpy incompatible: {weights} "
                              "(se requieren 1304 bytes y firma GRMP0001)")
        self.weights_path = str(weights)
        print(f"PICOSARGON ADAPTER v0.6.181 engine={executable} network={weights}", file=sys.stderr, flush=True)
        effective_timeout = max(int(timeout_ms), self.tmax_ms + 10000)
        super().__init__([executable, str(weights)], movetime_ms=self.tmax_ms,
                         timeout_ms=effective_timeout, label="PICOSARGON")
        self._send(f"setoption name QDepth value {self.qdepth}")
        self._send("isready")
        self._wait("readyok")

    def choose(self, board: chess.Board) -> MoveChoice:
        start = time.monotonic()
        self._send("position fen " + board.fen())
        self._send(f"go depth {self.depth} movetime {self.tmax_ms}")
        best = None
        # Preserve reported depth/score/nodes and ignore benign info lines.
        depth = nodes = score = 0
        deadline = start + self.timeout_ms / 1000
        while time.monotonic() < deadline:
            line = self._wait_any(deadline)
            if line.startswith("info "):
                words=line.split()
                for k, target in (("depth", "depth"), ("nodes", "nodes")):
                    if k in words:
                        try:
                            v=int(words[words.index(k)+1])
                            if target=="depth": depth=v
                            else: nodes=v
                        except (ValueError, IndexError):pass
                if "score" in words:
                    try:
                        idx=words.index("score")
                        if words[idx+1]=="cp": score=int(words[idx+2])
                    except (ValueError,IndexError):pass
            elif line.startswith("bestmove "):
                best=line.split()[1]
                break
        if best is None:
            raise PlayerError("picoSargon no entregó bestmove")
        move=None if best in ('0000','(none)') else chess.Move.from_uci(best)
        if move is not None and move not in board.legal_moves:
            raise PlayerError(f"picoSargon devolvió movimiento ilegal: {best}")
        return MoveChoice(move, score, depth, nodes, (time.monotonic()-start)*1000, self.name)

    def _wait_any(self, deadline):
        import queue
        remain = deadline-time.monotonic()
        if remain<=0:raise PlayerError("timeout picoSargon esperando bestmove")
        try: line=self.q.get(timeout=remain)
        except queue.Empty as exc:raise PlayerError("timeout picoSargon esperando bestmove") from exc
        if line is None:raise PlayerError("picoSargon finalizó inesperadamente")
        return line
