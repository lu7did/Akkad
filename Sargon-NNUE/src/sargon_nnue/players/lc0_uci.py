#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* lc0_uci.py
#* Monolithic Lc0 UCI player. Must be paired with evaluator=null.
#* v0.6.153
#=================================================================================================================*
"""Monolithic Lc0 UCI player. Must be paired with evaluator=null."""
from __future__ import annotations
import time
import chess
import chess.engine
from .base import Player,PlayerError
from ..types import MoveChoice,MATE_CP
from ..lc0_uci_common import create_engine

class LC0UCIPlayer(Player):
    name='LC0-UCI'
    def __init__(self,command,*,weights=None,backend='auto',backend_options='',threads=1,
                 nncache=200000,uci_options=None,depth=0,nodes=800,movetime_ms=0,
                 timeout_ms=60000,telemetry=None):
        self.depth=int(depth);self.nodes=int(nodes);self.movetime_ms=int(movetime_ms)
        if min(self.depth,self.nodes,self.movetime_ms)<0 or not any((self.depth,self.nodes,self.movetime_ms)):
            raise PlayerError('LC0 requiere un límite de búsqueda (depth/nodes/movetime) no negativo')
        self.telemetry=telemetry
        self.engine=create_engine(command,weights=weights,backend=backend,backend_options=backend_options,
                                  threads=threads,nncache=nncache,options=uci_options,timeout_ms=timeout_ms)
        self._game=object()
    def new_game(self):
        self._game=object()
    def choose(self,board:chess.Board)->MoveChoice:
        start=time.monotonic()
        limit=chess.engine.Limit(depth=self.depth or None,nodes=self.nodes or None,
                                 time=self.movetime_ms/1000.0 if self.movetime_ms else None)
        result=self.engine.play(board,limit,game=self._game,info=chess.engine.INFO_ALL)
        move=result.move
        if move is not None and move not in board.legal_moves:
            raise PlayerError(f'LC0-UCI devolvió jugada ilegal: {move.uci()}')
        info=result.info or {}
        score=0
        if info.get('score') is not None:
            value=info['score'].pov(chess.WHITE).score(mate_score=MATE_CP)
            if value is not None:score=int(value)
        return MoveChoice(move,score,int(info.get('depth',0)),int(info.get('nodes',0)),
                          (time.monotonic()-start)*1000,self.name)
    def close(self):
        if getattr(self,'engine',None) is not None:
            engine,self.engine=self.engine,None
            engine.quit()
