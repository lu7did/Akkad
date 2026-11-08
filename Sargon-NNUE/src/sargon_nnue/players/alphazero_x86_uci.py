"""Native AlphaZero-X86 UCI player. Neural inference runs inside AlphaZero.exe."""
from __future__ import annotations
import os
import sys
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
        cores_env=os.environ.get('AKKAD_AZ_CORES','1')
        try:
            cores=max(1,min(256,int(cores_env)))
        except ValueError as exc:
            raise PlayerError(f'Invalid AKKAD_AZ_CORES: {cores_env}') from exc
        print(f"⚙️ AlphaZero launcher executable={exe}", file=sys.stderr, flush=True)
        print(f"⚙️ AlphaZero launcher network={weights}", file=sys.stderr, flush=True)
        print(f"⚙️ AlphaZero launcher backend={self.backend} cores={cores}", file=sys.stderr, flush=True)
        super().__init__([str(exe),'--weights',str(weights),'--backend',self.backend,
                          '--backend-options',self.backend_options,'--cores',str(cores)],
                         movetime_ms=max(self.tmax_ms,1), timeout_ms=max(int(timeout_ms),self.tmax_ms+10000),
                         label=self.name, inherit_stderr=True)
        self._send(f'setoption name Simulations value {self.simulations}')
        self._send(f'setoption name Cpuct value {self.cpuct}')
        self._send(f'setoption name TMax value {self.tmax_ms}')
        self._send(f'setoption name Timeout value {int(timeout_ms)}')
        self._send('isready');self._wait('readyok')
    def choose(self,board:chess.Board,go_command:str|None=None)->MoveChoice:
        start=time.monotonic()
        root=board.root()
        pos='position startpos' if root.fen()==chess.Board().fen() else 'position fen '+root.fen()
        if board.move_stack:pos+=' moves '+' '.join(m.uci() for m in board.move_stack)
        self._send(pos)
        # Forward original clock semantics. The simulation limit remains an
        # upper bound; never replace wtime/btime with a fixed movetime.
        allowed={'wtime','btime','winc','binc','movestogo','movetime','nodes'}
        tokens=(go_command or '').split()
        options=[]
        if tokens and tokens[0]=='go':
            for i in range(1,len(tokens)-1):
                if tokens[i] in allowed:
                    try:
                        val=max(0,int(tokens[i+1]))
                    except ValueError:
                        continue
                    options.extend((tokens[i],str(val)))
        options_string=' '.join(options)
        if options_string:
            # Use configured simulation cap unless an explicit nodes cap was sent.
            if 'nodes' not in options:options_string+=f' nodes {self.simulations}'
            self._send('go '+options_string)
        else:
            self._send(f'go nodes {self.simulations}'+(f' movetime {self.tmax_ms}' if self.tmax_ms else ''))
        depth=0;nodes=0;score_stm=0;best=None
        self.last_uci_info = []
        deadline=start+self.timeout_ms/1000
        while time.monotonic()<deadline:
            try:line=self.q.get(timeout=max(.001,deadline-time.monotonic()))
            except queue.Empty:break
            if line is None:raise PlayerError('AlphaZero-X86 terminated')
            if line.startswith('info '):
                # Preserve the actual native UCI info for the TCP client.
                self.last_uci_info.append(line)
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
