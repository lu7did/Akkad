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
#* training.py
#* Implementa funciones del modulo training
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations
import math
import chess, chess.pgn
import numpy as np
from .evaluators.npz import NpzEvaluator

class TrainingRejected(RuntimeError): pass

class NpzTrainer:
    def __init__(self,evaluator:NpzEvaluator,lr:float=0.01): self.ev=evaluator; self.lr=float(lr)
    @staticmethod
    def target(result:str)->float|None:
        return {"1-0":1.0,"0-1":0.0,"1/2-1/2":0.5}.get(result)
    def train_board(self,board:chess.Board,target:float)->float:
        features=self.ev.active_features(board); acc,hidden,raw=self.ev.forward_raw(board)
        pred=1/(1+math.exp(-max(-15,min(15,raw)))); err=pred-target; delta=err*pred*(1-pred)
        old_who=self.ev.w_ho.copy()
        self.ev.w_ho -= self.lr*delta*hidden.reshape(-1,1); self.ev.b_o -= self.lr*delta
        self.ev.hm_w -= self.lr*delta*(board.halfmove_clock/50.0)
        hdelta=(delta*old_who.T).flatten(); hdelta[acc<=0]=0
        for f in features: self.ev.w_ih[f] -= self.lr*hdelta
        self.ev.b_h -= self.lr*hdelta
        return err*err
    def train_game(self,game:chess.pgn.Game)->tuple[int,float]:
        t=self.target(game.headers.get("Result","*"))
        if t is None: return 0,0.0
        board=game.board(); n=0; loss=0.0
        for move in game.mainline_moves():
            if move not in board.legal_moves: break
            board.push(move)
            if board.is_game_over(claim_draw=True): continue
            loss+=self.train_board(board,t); n+=1
        return n,(loss/n if n else 0.0)
