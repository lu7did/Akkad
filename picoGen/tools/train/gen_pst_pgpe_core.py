"""Linear exact features for the existing Sargon-inspired PST score (FP32 PGPE).

This is NOT a new PST heuristic: features reproduce gen_sargon_core._one_side,
material_phase and evaluate, with CALIBRATION_SCALE fixed to 100.
"""
from __future__ import annotations
import numpy as np
import chess
from gen_fp32_core import PST_LIMITS
from gen_fp32_core import pst_evaluate
from gen_fp32_core import DEFAULTS
from gen_sargon_core import material_phase, is_passed, CENTER

NAMES = tuple(k for k in DEFAULTS if k != 'CALIBRATION_SCALE')
START = dict(DEFAULTS, KNIGHT_VALUE=300, BISHOP_VALUE=300)
BASE = np.asarray([START[k] for k in NAMES],dtype=np.float32)
# Pawn is a positive material component; the other bounds retain historical specs.
LIMITS = {**PST_LIMITS, 'PAWN_VALUE': (1., 2047.)}
STEPS = np.asarray([25. if 'VALUE' in k else 5. for k in NAMES],dtype=np.float32)
LO = np.asarray([LIMITS[k][0] for k in NAMES],dtype=np.float32)
HI = np.asarray([LIMITS[k][1] for k in NAMES],dtype=np.float32)
MODEL_FORMAT='picogen-binpack-genetic-fp32-v1'

def decode(z):
    """Normalized PGPE search coordinates -> bounded FP32 PST coefficients."""
    g=np.asarray(z,dtype=np.float32)
    return np.clip(BASE+STEPS*g,LO,HI)

def params(g):
    return {**{k:float(v) for k,v in zip(NAMES,g)}, 'CALIBRATION_SCALE':100.0}

def features(board):
    if not board.is_valid():raise ValueError('Invalid PST board')
    d={k:0. for k in NAMES}
    if board.is_checkmate():return np.zeros(len(NAMES),np.float32), (-2000. if board.turn else 2000.)
    if board.is_stalemate() or board.is_insufficient_material():
        return np.zeros(len(NAMES),np.float32),0.
    opening=material_phase(board);endgame=1.-opening
    for color,sign in ((chess.WHITE,1.),(chess.BLACK,-1.)):
        pawns=list(board.pieces(chess.PAWN,color));pawn_set=set(pawns)
        king=board.king(color);enemy_king=board.king(not color)
        if king is None or enemy_king is None: raise ValueError('Missing king')
        for pt,name in ((chess.PAWN,'PAWN_VALUE'),(chess.KNIGHT,'KNIGHT_VALUE'),
                        (chess.BISHOP,'BISHOP_VALUE'),(chess.ROOK,'ROOK_VALUE'),(chess.QUEEN,'QUEEN_VALUE')):
            d[name]+=sign*len(board.pieces(pt,color))
        for pt,name,scale in ((chess.KNIGHT,'KNIGHT_CENTRALITY',6),
                              (chess.BISHOP,'BISHOP_CENTRALITY',6),(chess.ROOK,'ROOK_ACTIVITY',6)):
            for sq in board.pieces(pt,color):
                f=chess.square_file(sq);r=chess.square_rank(sq)
                d[name]+=sign*(min(f,7-f)+min(r,7-r))/scale
        for pt,name in ((chess.KNIGHT,'KNIGHT_MOBILITY'),(chess.BISHOP,'BISHOP_MOBILITY'),
                        (chess.ROOK,'ROOK_MOBILITY'),(chess.QUEEN,'QUEEN_MOBILITY')):
            for sq in board.pieces(pt,color):
                d[name]+=sign*sum(board.color_at(t)!=color for t in board.attacks(sq))
        home=0 if color else 7
        for pt in (chess.KNIGHT,chess.BISHOP):
            for sq in board.pieces(pt,color):
                if chess.square_rank(sq)!=home:d['MINOR_DEVELOPMENT']+=sign*opening
        queen_home=chess.D1 if color else chess.D8
        if queen_home not in board.pieces(chess.QUEEN,color) and len(board.pieces(chess.QUEEN,color)):
            d['EARLY_QUEEN_PENALTY']-=sign*opening
        d['CENTER_CONTROL']+=sign*sum(bool(board.attackers(color,sq)) for sq in CENTER)
        if king in ((chess.G1,chess.C1) if color else (chess.G8,chess.C8)):
            d['CASTLED_KING']+=sign*opening
        kr=chess.square_rank(king);kf=chess.square_file(king)
        front=kr+(1 if color else -1)
        if 0<=front<8:
            for f in range(max(0,kf-1),min(7,kf+1)+1):
                if chess.square(f,front) not in pawn_set:
                    d['KING_SHIELD_MISSING']-=sign*opening
        kcenter=min(kf,7-kf)+min(kr,7-kr)
        d['KING_ENDGAME_ACTIVITY']+=sign*endgame*kcenter/6
        file_count=[0]*8
        for sq in pawns:file_count[chess.square_file(sq)]+=1
        d['DOUBLED_PAWN']-=sign*sum(max(0,n-1) for n in file_count)
        for sq in pawns:
            f=chess.square_file(sq);r=chess.square_rank(sq)
            adjacent=[t for t in pawns if abs(chess.square_file(t)-f)==1]
            if not adjacent:d['ISOLATED_PAWN']-=sign
            if any(abs(chess.square_rank(t)-r)<=1 for t in adjacent):d['CONNECTED_PAWN']+=sign
            if is_passed(board,sq,color):
                relative=(r+1) if color else (8-r)
                if 2<=relative<=7:d[f'PASSED_RANK_{relative}']+=sign
                protected=any(t in pawn_set for t in board.attackers(color,sq)
                              if board.piece_type_at(t)==chess.PAWN)
                if protected:d['PROTECTED_PASSED_PAWN']+=sign
    # Matches legacy default tactical=True: immediate mate in one overrides score.
    for mv in board.legal_moves:
        board.push(mv)
        checkmate=board.is_checkmate()
        board.pop()
        if checkmate:return np.zeros(len(NAMES),np.float32),(2000. if board.turn else -2000.)
    return np.asarray([d[k] for k in NAMES],dtype=np.float32),np.nan

def forward(x,bias,weights):
    """Predicted white-perspective centipawns, with legacy ±2000 saturation."""
    pred=np.asarray(x,dtype=np.float64)@np.asarray(weights,dtype=np.float64).T
    np.clip(pred,-2000.,2000.,out=pred)
    mask=np.isfinite(bias)
    if np.any(mask):pred[mask,:]=np.asarray(bias)[mask,None]
    return pred

def verify(features_and_boards, tol=0.005):
    base=params(BASE)
    for b,feat,override in features_and_boards:
        predicted=float(override) if np.isfinite(override) else float(np.clip(feat.astype(np.float64)@BASE.astype(np.float64),-2000,2000))
        actual=float(pst_evaluate(b,base))
        if abs(predicted-actual)>tol:
            raise AssertionError(f'PST feature parity failed: {predicted} != {actual} fen={b.fen()}')
