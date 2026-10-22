"""TinyGyal-8 PyTorch evaluator; no LC0 subprocess or LC0 Python bindings.

This is a testable independent implementation. Numerical parity with LC0/Eigen
must be established using scripts/test_tinygyal_parity.py before production.
"""
from __future__ import annotations
from collections import OrderedDict
from hashlib import sha256
from math import isfinite, atanh
from dataclasses import dataclass
from pathlib import Path
import chess
import numpy as np
import torch
from .base import Evaluator, EvaluatorError
from .tinygyal_core import TinyGyalTorch
@dataclass(frozen=True)
class NeuralEvaluation:
    policy: dict
    w: float
    d: float
    l: float
    history: str
    network_id: str
    @property
    def q(self): return self.w-self.l


def wdl_from_qd(q,d):
    if not (isfinite(q) and isfinite(d)) or not -1.0001 <= q <= 1.0001 or not -0.0001 <= d <= 1.0001:
        raise EvaluatorError(f'TinyGyal invalid neural value q={q} d={d}')
    w=(1-d+q)/2
    l=(1-d-q)/2
    a=[max(0.,w),max(0.,d),max(0.,l)]
    t=sum(a)
    if t<=0: raise EvaluatorError('TinyGyal WDL normalization failed')
    return tuple(x/t for x in a)


def cp_from_q(q,scale):
    return round(scale*2*atanh(max(-0.999,min(0.999,q))))

# LC0 convolutional policy: 56 queen rays, 8 knight jumps, 9 underpromotions.
# The final 7 channels in TinyGyal's 80-channel convolution head are unused.
_RAYS=((0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1),(-1,0),(-1,1))
_KNIGHTS=((1,2),(2,1),(2,-1),(1,-2),(-1,-2),(-2,-1),(-2,1),(-1,2))


def _history(board):
    moves=list(board.move_stack)
    root=board.root() if moves else board.copy(stack=False)
    incomplete=root.fen()!=chess.Board().fen()
    states=[root.copy(stack=True)]
    for m in moves:
        nxt=states[-1].copy(stack=True)
        nxt.push(m)
        states.append(nxt)
    return states, ('INCOMPLETE' if incomplete else 'COMPLETE')


def encode_planes(board):
    """LC0 INPUT_CLASSICAL_112_PLANE, from current side's perspective.

    The moving side is always 'ours'; black positions are vertically mirrored.
    Older positions keep the same perspective as the current side.
    """
    states,history=_history(board)
    us=board.turn
    planes=np.zeros((112,8,8),dtype=np.float32)
    # LC0 classical 112-plane FillEmptyHistory.FEN_ONLY semantics:
    # An isolated non-startpos FEN repeats its earliest available position
    # in the missing history slots, rather than leaving those planes zero.
    # Complete histories originating from startpos keep missing slots zero.
    recent=list(reversed(states[-8:]))
    if history == 'INCOMPLETE' and recent:
        recent.extend([states[0]] * (8-len(recent)))
    for h,st in enumerate(recent):
        for sq,piece in st.piece_map().items():
            f=chess.square_file(sq)
            r=chess.square_rank(sq) if us==chess.WHITE else 7-chess.square_rank(sq)
            channel=h*13+(0 if piece.color==us else 6)+(piece.piece_type-1)
            planes[channel,r,f]=1.0
        if st.is_repetition(2):
            planes[h*13+12,:,:]=1.0
    # Legacy planes: our queenside/kingside, their queenside/kingside.
    for col,base in ((us,0),(not us,2)):
        if st_has_castle(board,col,False):planes[104+base,:,:]=1.0
        if st_has_castle(board,col,True):planes[104+base+1,:,:]=1.0
    if us==chess.BLACK:planes[108,:,:]=1.0
    planes[109,:,:]=float(board.halfmove_clock)
    planes[111,:,:]=1.0
    return planes,history


def st_has_castle(board,color,kingside):
    if kingside:return bool(board.has_kingside_castling_rights(color))
    return bool(board.has_queenside_castling_rights(color))


def _policy_slot(board,move):
    us=board.turn
    f0=chess.square_file(move.from_square)
    r0=chess.square_rank(move.from_square) if us else 7-chess.square_rank(move.from_square)
    # LC0 represents castling internally as king-to-rook, irrespective of
    # python-chess's standard king-to-final-square e1g1 / e1c1 notation.
    # Apply this only for the NN policy index; do not modify the legal move.
    target=move.to_square
    if board.is_castling(move) and not board.chess960:
        kingside=chess.square_file(move.to_square)>chess.square_file(move.from_square)
        target=chess.square(7 if kingside else 0,chess.square_rank(move.from_square))
    f1=chess.square_file(target)
    r1=chess.square_rank(target) if us else 7-chess.square_rank(target)
    df,dr=f1-f0,r1-r0
    if move.promotion in (chess.QUEEN,chess.BISHOP,chess.ROOK):
        if dr!=1 or abs(df)>1:raise EvaluatorError('Invalid underpromotion geometry')
        # LC0 policy map: underpromotion channels R, B, Q; knight uses the ordinary move ray.
        plane=64+(df+1)*3+({chess.ROOK:0,chess.BISHOP:1,chess.QUEEN:2}[move.promotion])
    elif (df,dr) in _KNIGHTS:
        plane=56+_KNIGHTS.index((df,dr))
    else:
        n=max(abs(df),abs(dr))
        if n<1 or n>7 or (df and dr and abs(df)!=abs(dr)):
            raise EvaluatorError(f'Unknown policy direction: {move}')
        direction=(0 if df==0 else (1 if df>0 else -1),0 if dr==0 else (1 if dr>0 else -1))
        plane=_RAYS.index(direction)*7+n-1
    return plane,r0,f0


class TinyGyalEvaluator(Evaluator):
    name='TINYGYAL'
    def __init__(self,network,*,backend='auto',backend_options='',history_mode='allow-incomplete',cache_size=10000,cp_scale=400.):
        if not network:raise EvaluatorError('TinyGyal requires external network .pb.gz')
        path=Path(network).expanduser().resolve()
        if not path.is_file():raise EvaluatorError(f'TinyGyal weights missing: {path}')
        if not str(path).lower().endswith('.pb.gz'):raise EvaluatorError('TinyGyal requires .pb.gz')
        if history_mode not in ('strict','allow-incomplete'):raise EvaluatorError('Invalid history_mode')
        if int(cache_size)<0:raise EvaluatorError('Invalid cache_size')
        self.network_id=sha256(path.read_bytes()).hexdigest()
        self.weights_file=path
        self.history_mode=history_mode
        self.cp_scale=float(cp_scale)
        self.cache_size=int(cache_size)
        self._cache=OrderedDict()
        # auto defaults to CPU to avoid surprising GPU latency and initialization.
        name=str(backend).lower()
        if name in ('auto','cpu','eigen','blas'):device='cpu'
        elif name in ('xpu','torch-xpu'):device='xpu'
        elif name in ('cuda','torch-cuda'):device='cuda'
        else:raise EvaluatorError(f'TinyGyal torch backend unsupported: {backend}')
        if device=='xpu' and (not hasattr(torch,'xpu') or not torch.xpu.is_available()):raise EvaluatorError('PyTorch Intel XPU unavailable')
        if device=='cuda' and not torch.cuda.is_available():raise EvaluatorError('PyTorch CUDA unavailable')
        self.device=device
        try:self.net=TinyGyalTorch(str(path)).to(device).eval()
        except Exception as exc:raise EvaluatorError(f'TinyGyal load failed: {exc}') from exc

    def new_game(self):self._cache.clear()
    def close(self):self._cache.clear()

    def evaluate_pv(self,board):
        if board.is_game_over(claim_draw=True):
            result=board.outcome(claim_draw=True)
            q=0 if result.winner is None else (1 if result.winner==board.turn else -1)
            return NeuralEvaluation({},float(q==1),float(q==0),float(q==-1),'TERMINAL',self.network_id)
        states,history=_history(board)
        if history=='INCOMPLETE' and self.history_mode=='strict':
            raise EvaluatorError('TinyGyal requires complete history')
        key=(states[0].fen(),tuple(m.uci() for m in board.move_stack),board.fen())
        if key in self._cache:
            value=self._cache.pop(key);self._cache[key]=value;return value
        x,history=encode_planes(board)
        with torch.inference_mode():
            policy,q=self.net(torch.from_numpy(x[None]).to(self.device))
            policy=policy[0].to('cpu').numpy()
            q=float(q[0,0].item())
        legal=list(board.legal_moves)
        logits=np.array([float(policy[_policy_slot(board,m)]) for m in legal],dtype=np.float64)
        logits-=logits.max()
        weights=np.exp(logits)
        weights/=weights.sum()
        if not isfinite(q) or np.any(~np.isfinite(weights)):raise EvaluatorError('TinyGyal non-finite result')
        w,d,l=wdl_from_qd(q,0.)
        result=NeuralEvaluation(dict(zip(legal,map(float,weights))),w,d,l,history,self.network_id)
        if self.cache_size:
            self._cache[key]=result
            if len(self._cache)>self.cache_size:self._cache.popitem(last=False)
        return result

    def evaluate(self,board):
        q=self.evaluate_pv(board).q
        cp=cp_from_q(q,self.cp_scale)
        return cp if board.turn==chess.WHITE else -cp
