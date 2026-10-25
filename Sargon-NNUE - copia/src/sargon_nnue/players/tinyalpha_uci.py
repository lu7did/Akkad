"""Independent native tinyAlpha UCI player; evaluator must be NULL."""
from __future__ import annotations
import queue
import time
from pathlib import Path
import chess
from .uci_external import ExternalUCIPlayer
from .base import PlayerError
from ..types import MoveChoice

class TinyAlphaUCIPlayer(ExternalUCIPlayer):
    name = 'TINYALPHA'

    def __init__(self, executable, network, *, simulations=2000, cpuct=1.5, tmax_ms=15000, timeout_ms=30000):
        exe=Path(executable).expanduser().resolve()
        weights=Path(network).expanduser().resolve() if network else None
        if not exe.is_file():raise PlayerError(f'tinyAlpha executable missing: {exe}')
        if weights is None or not weights.is_file():raise PlayerError(f'tinyAlpha external network missing: {weights}')
        self.simulations=int(simulations)
        self.cpuct=float(cpuct)
        self.tmax_ms=int(tmax_ms)
        if self.simulations<1 or self.cpuct<=0 or self.tmax_ms<1:
            raise PlayerError('tinyAlpha requires simulations>=1 cpuct>0 tmax>=1')
        super().__init__([str(exe),'--network',str(weights), '--simulations',str(self.simulations), '--cpuct',str(self.cpuct)],
                         movetime_ms=self.tmax_ms, timeout_ms=max(int(timeout_ms),self.tmax_ms+10000), label=self.name)

    def choose(self, board:chess.Board)->MoveChoice:
        start=time.monotonic()
        root=board.root()
        if root.fen()==chess.Board().fen():position='position startpos'
        else:position='position fen '+root.fen()
        if board.move_stack:position+=' moves '+' '.join(m.uci() for m in board.move_stack)
        self._send(position)
        self._send(f'go nodes {self.simulations} movetime {self.tmax_ms}')
        depth=0; nodes=0; score=0
        deadline=start+self.timeout_ms/1000
        best=None
        while time.monotonic()<deadline:
            try:line=self.q.get(timeout=max(.001,deadline-time.monotonic()))
            except queue.Empty:break
            if line is None:raise PlayerError('tinyAlpha terminated unexpectedly')
            if line.startswith('info '):
                words=line.split()
                for name in ('nodes','depth'):
                    if name in words:
                        try:
                            n=int(words[words.index(name)+1]);
                            if name=='nodes':nodes=n
                            else:depth=n
                        except (ValueError,IndexError):pass
                if 'score' in words:
                    try:
                        i=words.index('score');
                        if words[i+1]=='cp':score=int(words[i+2])
                    except (ValueError,IndexError):pass
            elif line.startswith('bestmove '):best=line.split()[1];break
        if best is None:raise PlayerError('tinyAlpha timed out waiting for bestmove')
        move=None if best in ('0000','(none)') else chess.Move.from_uci(best)
        if move is not None and move not in board.legal_moves:raise PlayerError(f'tinyAlpha illegal move: {best}')
        return MoveChoice(move,score,depth,nodes,(time.monotonic()-start)*1000,self.name)
