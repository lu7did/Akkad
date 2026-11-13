"""MCTSP + MCTSE: PUCT search with Tiny NNUE (780x16 two heads).

Uses legal chess positions, per-side perspective, quantized INT8 checkpoint.
No model training and no network calls occur in this module.
"""
import math
import time
from dataclasses import dataclass,field


def feature_indices(board):
    import chess
    side=board.turn;out=[]
    for sq,p in board.piece_map().items():
        kind=p.piece_type-1+(0 if p.color==side else 6)
        ix=(7-chess.square_rank(sq))*8+chess.square_file(sq)
        if not side:ix=63-ix
        out.append(kind*64+ix)
    for ix,color,kingside in ((768,side,True),(769,side,False),(770,not side,True),(771,not side,False)):
        if (board.has_kingside_castling_rights(color) if kingside else board.has_queenside_castling_rights(color)):
            out.append(ix)
    if board.ep_square is not None:
        col=chess.square_file(board.ep_square)
        out.append(772+(col if side else 7-col))
    return sorted(out)


def square_index(sq,turn):
    import chess
    idx=(7-chess.square_rank(sq))*8+chess.square_file(sq)
    return idx if turn else 63-idx


class TinyEvaluator:
    def __init__(self,network):
        if not network:raise ValueError('MCTSE requiere evaluator.network con checkpoint .pt')
        import torch
        self.torch=torch
        try:
            ckpt=torch.load(network,map_location='cpu',weights_only=True)
        except Exception as exc:
            raise ValueError(f'checkpoint NNUE no disponible o inválido: {network}: {exc}') from exc
        conf=ckpt.get('config',{})
        if (conf.get('features'),conf.get('hidden'),conf.get('policy'),conf.get('value')) != (780,16,'from_to','tanh'):
            raise ValueError('MCTSE requiere checkpoint 780x16 from_to tanh de picoAlpha')
        if ckpt.get('format') != 'picoalpha-nnue-int8-v1':
            raise ValueError('MCTSE requiere checkpoint INT8 exportado por picoAlpha export.py --int8')
        expected={'W_INPUT':(780,16),'W_VALUE':(1,16),
                  'W_FROM':(64,16),'W_TO':(64,16)}
        weights=ckpt.get('weights',{})
        scales=ckpt.get('scales',{})
        if set(weights)!=set(expected) or set(scales)!=set(expected):
            raise ValueError('Checkpoint INT8: faltan matrices o escalas')
        if any(tuple(weights[k].shape)!=shape or weights[k].dtype!=torch.int8 for k,shape in expected.items()):
            raise ValueError('Checkpoint INT8: dimensiones/tipo incompatibles')
        if any(not math.isfinite(float(scales[k])) or float(scales[k])<=0 for k in expected):
            raise ValueError('Checkpoint INT8: escalas invalidas')
        self.weights={k:v.cpu().contiguous().to(torch.int32) for k,v in weights.items()}
        self.scales={k:float(v) for k,v in scales.items()}
        self.network=str(network)
        self.evaluations=0

    def evaluate(self,board,moves=None):
        torch=self.torch
        with torch.no_grad():
            idx=torch.tensor(feature_indices(board),dtype=torch.long)
            # Both the sparse accumulation and projection products use INTEGER arithmetic.
            hidden=self.weights['W_INPUT'].index_select(0,idx).sum(dim=0).clamp(min=0).to(torch.int32)
            scale=self.scales['W_INPUT']
            value_raw=int(torch.mv(self.weights['W_VALUE'],hidden)[0].item())
            value=math.tanh(value_raw*scale*self.scales['W_VALUE'])
            self.evaluations+=1
            if moves is None or not moves:return value,{}
            frm=self.weights['W_FROM'].matmul(hidden).tolist()
            to=self.weights['W_TO'].matmul(hidden).tolist()
            scale_from=scale*self.scales['W_FROM']
            scale_to=scale*self.scales['W_TO']
            logits=[frm[square_index(m.from_square,board.turn)]*scale_from+
                    to[square_index(m.to_square,board.turn)]*scale_to for m in moves]
            max_logit=max(logits)
            exp_logits=[math.exp(v-max_logit) for v in logits]
            total=sum(exp_logits)
            return value,dict(zip(moves,(v/total for v in exp_logits)))

    def close(self):pass


@dataclass
class Node:
    move:object=None
    prior:float=0.0
    visits:int=0
    value_sum:float=0.0
    children:list=field(default_factory=list)
    expanded:bool=False


def select(node,cpuct):
    root=math.sqrt(max(1,node.visits))
    return max(node.children,key=lambda ch:(-ch.value_sum/ch.visits if ch.visits else 0.0)
               +cpuct*ch.prior*root/(1+ch.visits))


def terminal_value(board):
    import chess
    outcome=board.outcome(claim_draw=True)
    if outcome is None:return None
    if outcome.winner is None:return 0.0
    return 1.0 if outcome.winner==board.turn else -1.0


def search(board,evaluator,sims=200,timeout=30000,tmax=15000,depth=12,cpuct=1.4):
    """Value sums always use each node's side-to-move perspective.

    Hard wall-time checks occur before each simulation and traversal step;
    an individual PyTorch call cannot be interrupted mid-kernel.
    """
    if sims<1 or timeout<1 or tmax<1 or depth<1:raise ValueError('sims/timeout/tmax/depth deben ser positivos')
    started=time.monotonic();deadline=started+min(timeout,tmax)/1000.0
    root=Node();nodes=1;completed=0;max_depth=0
    root_legal=list(board.legal_moves)
    if not root_legal:
        return dict(move=None,simulations=0,nodes=1,elapsed_ms=0,depth=0,value=terminal_value(board) or 0.0,reason='terminal')
    if time.monotonic()>=deadline:raise TimeoutError('sin tiempo para expansión raíz')
    rv,prior=evaluator.evaluate(board,root_legal)
    root.children=[Node(move=m,prior=prior[m]) for m in root_legal];root.expanded=True;nodes+=len(root.children)
    # A legal fallback exists even if the budget is exhausted during the first NN inference.
    while completed<sims and time.monotonic()<deadline:
        b=board.copy(stack=True);node=root;trail=[root];level=0
        while node.expanded and node.children and level<depth and time.monotonic()<deadline:
            child=select(node,cpuct)
            b.push(child.move);node=child;trail.append(node);level+=1
        if time.monotonic()>=deadline:break
        value=terminal_value(b)
        if value is None:
            if time.monotonic()>=deadline:break
            legal=list(b.legal_moves) if level<depth else None
            value,priors=evaluator.evaluate(b,legal)
            if legal is not None and not node.expanded:
                node.children=[Node(move=m,prior=priors[m]) for m in legal]
                node.expanded=True;nodes+=len(node.children)
        for visited in reversed(trail):
            visited.visits+=1;visited.value_sum+=value;value=-value
        max_depth=max(max_depth,level);completed+=1
    best=max(root.children,key=lambda n:(n.visits,n.prior))
    value=-best.value_sum/best.visits if best.visits else rv
    reason='sims' if completed==sims else 'timeout'
    return dict(move=best.move,simulations=completed,nodes=nodes,
                elapsed_ms=max(1,int((time.monotonic()-started)*1000)),depth=max_depth,
                value=value,root_value=rv,reason=reason,visits=best.visits)
