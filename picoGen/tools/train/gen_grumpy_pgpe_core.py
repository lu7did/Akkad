"""Grumpy GRMP0001 feature/parameter contract in FP32, no quantization.

Reproduces picoSargon/ARM/reference/grumpy.py and x86/src/grumpy.cpp:
  192x8 factorized rank/file transform, shared two perspectives,
  8 output buckets, fixed material baseline.

Trainable layout: factor (192,8), factor biases (8),
                output bucket weights (8,16), bucket biases (8) = 1680.
"""
import csv
import random
from pathlib import Path

import numpy as np
import torch

FEATURES, UNITS, BUCKETS = 192, 8, 8
PARAMS = FEATURES * UNITS + UNITS + BUCKETS * (2*UNITS) + BUCKETS
FORMAT = 'picogen-grumpy-pgpe-fp32-v1'
MATERIAL_PACKED = 0x3847D12C4B064
MATERIAL = tuple((MATERIAL_PACKED >> (10*k)) & 1023 for k in range(6))
CP_SCALE = 400.0 / 1024.0


def factor_index(feature):
    group, square = divmod(int(feature), 64)
    return group*16 + square//8, group*16 + 8 + square%8


def from_board(board):
    """Inputs are side-to-move/other perspectives, 64 factor indices each.

    White perspective is converted to STM at the inputs; white-centipawn output
    multiplies the neural residual by +1 for white and -1 for black.
    """
    import chess
    pieces = list(board.piece_map().items())
    if not 2 <= len(pieces) <= 32:
        raise ValueError('Grumpy requires 2..32 pieces')
    acc = np.zeros((2,64),dtype=np.int16)
    idx = 0
    mat = 0
    for square, piece in pieces:
        color = piece.color
        kind = piece.piece_type - 1
        mat += MATERIAL[kind] * (1 if color == chess.WHITE else -1)
        white_feature = (0 if color == chess.WHITE else 384) + kind*64 + square
        black_feature = ((384 if color == chess.WHITE else 0) + kind*64 + square) ^ 56
        for perspective, feature in enumerate((white_feature,black_feature)):
            a,b = factor_index(feature)
            acc[perspective,2*idx] = a
            acc[perspective,2*idx+1] = b
        idx += 1
    if board.turn == chess.BLACK:
        acc = acc[::-1].copy()
    return acc, idx*2, (idx-2)//4, float(mat), (1 if board.turn == chess.WHITE else -1)


def load_csv(path, count, seed, *, exclude_zero=True, exclude_check=True,
             exclude_capture=True, overlap=None):
    """Seeded reservoir, requires canonical T79/T77 CSV columns.

    Scores are WHITE perspective, material is WHITE perspective, neural uses STM.
    """
    import chess
    from gen_csv_dataset import REQUIRED
    rng = random.Random(seed)
    sample=[]; keys=set(); accepted=0
    stats={'rows':0,'zero':0,'check':0,'capture':0,'unknown_move':0,'overlap':0,'invalid':0,'eligible':0}
    with open(path,encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or any(c not in reader.fieldnames for c in REQUIRED):
            raise ValueError('Invalid binpack CSV schema '+str(path))
        for row in reader:
            stats['rows'] += 1
            try:
                score=int(row['score_white_cp'])
                if exclude_zero and score == 0:
                    stats['zero']+=1;continue
                board=chess.Board(row['fen'])
                if not board.is_valid():raise ValueError('Invalid board')
                stm=int(row['score_stm_cp'])
                if score != (max(-2000,min(2000,stm))*(1 if board.turn else -1)):
                    raise ValueError('Score perspective mismatch')
                key=(board.board_fen(),board.turn,board.castling_xfen())
                if overlap is not None and key in overlap:
                    stats['overlap']+=1;continue
                if exclude_check and board.is_check():
                    stats['check']+=1;continue
                if exclude_capture:
                    move=chess.Move.from_uci(row['played_uci'].strip())
                    if move not in board.legal_moves:
                        stats['unknown_move']+=1;continue
                    if board.is_capture(move):
                        stats['capture']+=1;continue
                x,n,b,mat,stm_sign=from_board(board)
            except (ValueError,KeyError,TypeError):
                stats['invalid']+=1
                continue
            accepted+=1
            item=(x,n,b,mat,stm_sign,float(score),key)
            if len(sample)<count:sample.append(item)
            else:
                k=rng.randrange(accepted)
                if k<count:sample[k]=item
    if not sample:raise ValueError('No eligible Grumpy positions in '+str(path))
    stats['eligible']=accepted
    xs=np.stack([r[0] for r in sample]); ns=np.asarray([r[1] for r in sample],dtype=np.int64)
    buckets=np.asarray([r[2] for r in sample],dtype=np.int64)
    material=np.asarray([r[3] for r in sample],dtype=np.float32)
    signs=np.asarray([r[4] for r in sample],dtype=np.float32)
    y=np.asarray([r[5] for r in sample],dtype=np.float32)
    keys={r[6] for r in sample}
    print(f'GRUMPY CSV {Path(path).name}: {stats} selected={len(y)}',flush=True)
    return (xs,ns,buckets,material,signs,y), keys, stats


def to_torch(data, device='cpu'):
    x,n,b,m,s,y=data
    return (torch.as_tensor(x.astype(np.int64),device=device),
            torch.as_tensor(n,device=device),torch.as_tensor(b,device=device),
            torch.as_tensor(m,device=device),torch.as_tensor(s,device=device),
            torch.as_tensor(y,device=device))


def forward(weights, data):
    """Differentiable Grumpy FP32 white-perspective centipawn predictions.

    weights: [1680] or [population,1680]. data may be CPU or GPU tensors.
    """
    x, counts, buckets, material, stm_sign, _ = data
    if weights.shape[-1] != PARAMS:raise ValueError('Expected exactly 1680 FP32 weights')
    single=(weights.ndim==1)
    w=weights.reshape(-1,PARAMS)
    p=w.shape[0]; size=x.shape[0]
    factors=w[:,:1536].reshape(p,192,8)
    bias=w[:,1536:1544]
    output=w[:,1544:1672].reshape(p,8,16)
    out_bias=w[:,1672:1680]
    mask=(torch.arange(64,device=x.device)[None,:] < counts[:,None]).to(factors.dtype)
    channels=[]
    for side in range(2):
        gathered=factors[:,x[:,side,:].long(),:]
        pre=(gathered*mask[None,:,:,None]).sum(dim=2)+bias[:,None,:]
        channels.append(pre.clamp(0.0,32.0))
    hidden=torch.cat(channels,dim=-1)
    ob=output[:,buckets,:]
    # Grumpy baseline: 8 * output bucket bias, net from STM perspective.
    neural=(hidden*ob).sum(dim=-1)+8.0*out_bias[:,buckets]
    cp=material[None,:]+stm_sign[None,:]*CP_SCALE*neural
    return cp[0] if single else cp


def loss_parts(pred,target,cp_weight=1.0):
    """Both terms have meaningful scale; cp term is non-saturating."""
    target_p=torch.sigmoid(target/400.0)
    prob=(torch.sigmoid(pred/400.0)-target_p).square().mean(dim=-1)
    cp=((pred-target)/2000.0).square().mean(dim=-1)
    return prob+cp_weight*cp,prob,cp


def cp_objective(pred,target):
    """Only training criterion: mean squared error in Stockfish centipawns / 2000^2."""
    return ((pred-target)/2000.0).square().mean(dim=-1)


def metrics(pred,target):
    a=np.asarray(pred,dtype=np.float64)
    b=np.asarray(target,dtype=np.float64)
    err=a-b
    p=1/(1+np.exp(-np.clip(a/400,-80,80)))
    t=1/(1+np.exp(-np.clip(b/400,-80,80)))
    return {'rmse_cp':float(np.sqrt(np.mean(err*err))),
            'mae_cp':float(np.mean(np.abs(err))),
            'bias_cp':float(np.mean(err)),
            'mse_probability':float(np.mean((p-t)**2)),
            'mse_cp_normalized':float(np.mean((err/2000.0)**2)),
            'pred_std_cp':float(np.std(a)),
            'pred_min_cp':float(np.min(a)),
            'pred_max_cp':float(np.max(a))}
