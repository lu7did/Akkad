"""Native AlphaZero-X86 UCI player. Neural inference runs inside AlphaZero.exe."""
from __future__ import annotations
import queue
import time
from pathlib import Path
import chess
from .base import PlayerError
from .uci_external import ExternalUCIPlayer
from ..types import MoveChoice

class AlphaZeroX86UCIPlayer(ExternalUCIPlayer):
    name = 'AlphaZero-X86'
    def __init__(self, executable, network, *, simulations=128, cpuct=1.5,
                 tmax_ms=15000, backend='onnx-dml', backend_options='gpu=0', timeout_ms=60000):
        exe=Path(executable).expanduser().resolve() if executable else None
        weights=Path(network).expanduser().resolve() if network else None
        if not exe or not exe.is_file():raise PlayerError(f'AlphaZero-X86 executable missing: {exe}')
        if not weights or not weights.is_file():raise PlayerError(f'AlphaZero-X86 weights missing: {weights}')
        self.simulations=int(simulations);self.cpuct=float(cpuct);self.tmax_ms=int(tmax_ms)
        if self.simulations<1 or self.cpuct<=0 or self.tmax_ms<0:raise PlayerError('Invalid AlphaZero-X86 search parameters')
        self.backend=backend if backend not in ('auto',None) else 'onnx-dml'
        self.backend_options=backend_options if backend_options else ('gpu=0' if self.backend=='onnx-dml' else '')
        super().__init__([str(exe),'--weights',str(weights),'--backend',self.backend,
                          '--backend-options',self.backend_options],
                         movetime_ms=max(self.tmax_ms,1), timeout_ms=max(int(timeout_ms),self.tmax_ms+10000),label=self.name)
        self._send(f'setoption name Simulations value {self.simulations}')
        self._send(f'setoption name Cpuct value {self.cpuct}')
        self._send(f'setoption name TMax value {self.tmax_ms}')
        self._send(f'setoption name Timeout value {int(timeout_ms)}')
        self._send('isready');self._wait('readyok')
    def choose(self,board:chess.Board)->MoveChoice:
        start=time.monotonic()
        root=board.root()
        pos='position startpos' if root.fen()==chess.Board().fen() else 'position fen '+root.fen()
        if board.move_stack:pos+=' moves '+' '.join(m.uci() for m in board.move_stack)
        self._send(pos)
        self._send(f'go nodes {self.simulations}'+(f' movetime {self.tmax_ms}' if self.tmax_ms else ''))
        depth=0;nodes=0;score_stm=0;best=None
        deadline=start+self.timeout_ms/1000
        while time.monotonic()<deadline:
            try:line=self.q.get(timeout=max(.001,deadline-time.monotonic()))
            except queue.Empty:break
            if line is None:raise PlayerError('AlphaZero-X86 terminated')
            if line.startswith('info '):
                fields=line.split()
                for key in ('depth','nodes'):
                    if key in fields:
                        try:
                            value=int(fields[fields.index(key)+1])
                            if key=='depth':depth=value
                            else:nodes=value
                        except (ValueError,IndexError):pass
                if 'score' in fields:
                    try:
                        i=fields.index('score')
                        if fields[i+1]=='cp':score_stm=int(fields[i+2])
                    except (ValueError,IndexError):pass
            if line.startswith('bestmove '):best=line.split()[1];break
        if best is None:raise PlayerError('AlphaZero-X86 timeout waiting for bestmove')
        move=None if best in ('0000','(none)') else chess.Move.from_uci(best)
        if move is not None and move not in board.legal_moves:raise PlayerError(f'AlphaZero-X86 illegal move: {best}')
        score_white=score_stm if board.turn==chess.WHITE else -score_stm
        return MoveChoice(move,score_white,depth,nodes,(time.monotonic()-start)*1000,self.name)
