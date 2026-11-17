"""Sargon CLASSIC de Akkad v0.6.153: misma heurística que Sargon-NNUE/classic.py.
Implementación autónoma para auditoría, sin importar módulos de picoAlpha.
Centipeones desde perspectiva blanca.
"""
import chess
PIECE={chess.PAWN:100,chess.KNIGHT:320,chess.BISHOP:330,chess.ROOK:500,chess.QUEEN:900,chess.KING:0}
CENTER={chess.D4,chess.E4,chess.D5,chess.E5}
EXT_CENTER={chess.C3,chess.D3,chess.E3,chess.F3,chess.C4,chess.F4,chess.C5,chess.F5,chess.C6,chess.D6,chess.E6,chess.F6}

def evaluate(board):
    if board.is_checkmate():return -100000 if board.turn==chess.WHITE else 100000
    if board.is_game_over(claim_draw=True):return 0
    material=sum(PIECE[p.piece_type]*(1 if p.color else -1) for p in board.piece_map().values())
    activity=0.
    for sq,p in board.piece_map().items():
        sign=1. if p.color else -1.
        activity+=sign*1.5*len(board.attacks(sq))
        if sq in CENTER:activity+=sign*(10. if p.piece_type in (chess.PAWN,chess.KNIGHT,chess.BISHOP) else 4.)
        elif sq in EXT_CENTER:activity+=sign*2.5
        if p.piece_type==chess.KNIGHT:
            if sq in ((chess.B1,chess.G1) if p.color else (chess.B8,chess.G8)):activity-=sign*8.
        elif p.piece_type==chess.BISHOP:
            if sq in ((chess.C1,chess.F1) if p.color else (chess.C8,chess.F8)):activity-=sign*6.
    if len(board.pieces(chess.BISHOP,chess.WHITE))>=2:activity+=12.
    if len(board.pieces(chess.BISHOP,chess.BLACK))>=2:activity-=12.
    pawn=0.
    for color,sign in ((chess.WHITE,1.),(chess.BLACK,-1.)):
        files=[chess.square_file(sq) for sq in board.pieces(chess.PAWN,color)]
        counts={f:files.count(f) for f in set(files)}
        pawn-=sign*8.*sum(max(0,n-1) for n in counts.values())
        occupied=set(files)
        pawn-=sign*4.*sum(1 for f in occupied if f-1 not in occupied and f+1 not in occupied)
    king_score=0.
    for color,sign in ((chess.WHITE,1.),(chess.BLACK,-1.)):
        king=board.king(color)
        if king is None:continue
        if board.turn==color and board.is_check():king_score-=sign*35.
        kf,kr=chess.square_file(king),chess.square_rank(king)
        rr=kr+(1 if color else -1)
        if 0<=rr<8:
            for ff in (kf-1,kf,kf+1):
                if 0<=ff<8:
                    p=board.piece_at(chess.square(ff,rr))
                    if p and p.color==color and p.piece_type==chess.PAWN:king_score+=sign*5.
        ring=chess.SquareSet(chess.BB_KING_ATTACKS[king])
        king_score-=sign*3.5*sum(1 for sq in ring if board.is_attacked_by(not color,sq))
    return material+int(round(activity))+int(round(pawn))+int(round(king_score))
