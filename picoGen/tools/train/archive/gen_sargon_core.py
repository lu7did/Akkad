"""Sargon III-inspired *experimental* white-centipawn evaluation.

This is the proposed E*_S3 of the technical note of 2026-11-14, NOT an
historically reconstructed Sargon evaluation. The note's additive factors
are used; no undocumented polynomial cross products are invented.
"""
import chess

# Bounds are explicit genetic choices, not claims about historical Sargon.
# Chromosome: Gray coded signed 9-bit positional genes; 11-bit material genes.
DEFAULTS = {
 'PAWN_VALUE':100, 'KNIGHT_VALUE':310,'BISHOP_VALUE':314,'ROOK_VALUE':500,'QUEEN_VALUE':900,
 'KNIGHT_CENTRALITY':20,'BISHOP_CENTRALITY':12,'ROOK_ACTIVITY':12,
 'KNIGHT_MOBILITY':3,'BISHOP_MOBILITY':2,'ROOK_MOBILITY':1,'QUEEN_MOBILITY':1,
 'MINOR_DEVELOPMENT':8,'EARLY_QUEEN_PENALTY':12,'CENTER_CONTROL':3,
 'CASTLED_KING':20,'KING_SHIELD_MISSING':10,'KING_ENDGAME_ACTIVITY':25,
 'ISOLATED_PAWN':12,'DOUBLED_PAWN':10,'CONNECTED_PAWN':5,'PROTECTED_PASSED_PAWN':15,
 'PASSED_RANK_2':10,'PASSED_RANK_3':15,'PASSED_RANK_4':25,
 'PASSED_RANK_5':40,'PASSED_RANK_6':60,'PASSED_RANK_7':80,
 'CALIBRATION_SCALE':100,
}
# Positional terms are nonnegative (penalty signs are fixed by feature definition).
SPECS = [(k,11,0,2047) for k in ('KNIGHT_VALUE','BISHOP_VALUE','ROOK_VALUE','QUEEN_VALUE')] + [
 (k, 9, 0, 511) for k in DEFAULTS if k not in ('PAWN_VALUE','KNIGHT_VALUE','BISHOP_VALUE','ROOK_VALUE','QUEEN_VALUE','CALIBRATION_SCALE')
] + [('CALIBRATION_SCALE', 9, 1, 511)]
BITS=sum(spec[1] for spec in SPECS)
NAMES=tuple(x[0] for x in SPECS)
CENTER=(chess.D4,chess.E4,chess.D5,chess.E5)


def decode(bits):
    p={'PAWN_VALUE':100}; offset=0
    for name,width,lo,hi in SPECS:
        gray=0
        for v in bits[offset:offset+width]:gray=(gray<<1)|int(v)
        offset+=width
        binary=gray
        while gray>>1:
            gray>>=1;binary^=gray
        p[name]=lo+binary % (hi-lo+1)
    return p


def encode(p):
    out=[]
    for name,width,lo,hi in SPECS:
        value=int(p[name]);value=max(lo,min(hi,value))-lo
        gray=value^(value>>1)
        out.extend((gray>>shift)&1 for shift in range(width-1,-1,-1))
    return out


def is_passed(board, square, color):
    f=chess.square_file(square);r=chess.square_rank(square)
    for enemy in board.pieces(chess.PAWN,not color):
        er=chess.square_rank(enemy)
        if abs(chess.square_file(enemy)-f)<=1 and ((er>r) if color else (er<r)):
            return False
    return True


def material_phase(board):
    # Full non-pawn material per both sides: 2*(2N+2B+2R+Q)=24 phase units.
    count=sum(len(board.pieces(pt,c))*w for pt,w in ((chess.KNIGHT,1),(chess.BISHOP,1),(chess.ROOK,2),(chess.QUEEN,4)) for c in (True,False))
    return min(1.0,max(0.0,count/24.0))


def _one_side(board,color,p,opening,endgame):
    pawns=list(board.pieces(chess.PAWN,color)); pawn_set=set(pawns)
    enemy_king=board.king(not color); king=board.king(color)
    if king is None or enemy_king is None:raise ValueError('Posición inválida: falta un rey')
    pieces=board.piece_map();score=0.0
    for pt,name in ((chess.PAWN,'PAWN_VALUE'),(chess.KNIGHT,'KNIGHT_VALUE'),(chess.BISHOP,'BISHOP_VALUE'),(chess.ROOK,'ROOK_VALUE'),(chess.QUEEN,'QUEEN_VALUE')):
        score+=len(board.pieces(pt,color))*p[name]
    for pt,name,scale in ((chess.KNIGHT,'KNIGHT_CENTRALITY',6),(chess.BISHOP,'BISHOP_CENTRALITY',6),(chess.ROOK,'ROOK_ACTIVITY',6)):
        for sq in board.pieces(pt,color):
            f=chess.square_file(sq);r=chess.square_rank(sq)
            centrality=min(f,7-f)+min(r,7-r)
            score+=p[name]*centrality/scale
    for pt,name in ((chess.KNIGHT,'KNIGHT_MOBILITY'),(chess.BISHOP,'BISHOP_MOBILITY'),(chess.ROOK,'ROOK_MOBILITY'),(chess.QUEEN,'QUEEN_MOBILITY')):
        for sq in board.pieces(pt,color):
            # Distinct attacked squares that are not occupied by friendly pieces.
            destinations=sum(board.color_at(t)!=color for t in board.attacks(sq))
            score+=destinations*p[name]
    # Position-only development proxy. FEN cannot prove prior move history.
    home=0 if color else 7
    for pt in (chess.KNIGHT,chess.BISHOP):
        for sq in board.pieces(pt,color):
            if chess.square_rank(sq)!=home:score+=opening*p['MINOR_DEVELOPMENT']
    queen_home=chess.D1 if color else chess.D8
    if (queen_home not in board.pieces(chess.QUEEN,color)) and len(board.pieces(chess.QUEEN,color)):
        score-=opening*p['EARLY_QUEEN_PENALTY']
    center_attacks=sum(bool(board.attackers(color,sq)) for sq in CENTER)
    score+=center_attacks*p['CENTER_CONTROL']
    # Approximate current castled-king placement; never claim historic castling.
    if king in ((chess.G1,chess.C1) if color else (chess.G8,chess.C8)):
        score+=opening*p['CASTLED_KING']
    kr=chess.square_rank(king);kf=chess.square_file(king)
    front=kr+(1 if color else -1)
    if 0<=front<8:
        for f in range(max(0,kf-1),min(7,kf+1)+1):
            if chess.square(f,front) not in pawn_set:
                score-=opening*p['KING_SHIELD_MISSING']
    kcenter=min(kf,7-kf)+min(kr,7-kr)
    score+=endgame*p['KING_ENDGAME_ACTIVITY']*kcenter/6
    file_count=[0]*8
    for sq in pawns:file_count[chess.square_file(sq)]+=1
    score-=p['DOUBLED_PAWN']*sum(max(0,n-1) for n in file_count)
    for sq in pawns:
        f=chess.square_file(sq);r=chess.square_rank(sq)
        adjacent=[t for t in pawns if abs(chess.square_file(t)-f)==1]
        if not adjacent:score-=p['ISOLATED_PAWN']
        if any(abs(chess.square_rank(t)-r)<=1 for t in adjacent):score+=p['CONNECTED_PAWN']
        if is_passed(board,sq,color):
            relative=(r+1) if color else (8-r)
            if 2<=relative<=7:score+=p[f'PASSED_RANK_{relative}']
            protected=any(t in pawn_set for t in board.attackers(color,sq) if board.piece_type_at(t)==chess.PAWN)
            if protected:score+=p['PROTECTED_PASSED_PAWN']
    return score


def evaluate(board,p, *, tactical=True):
    if not board.is_valid():raise ValueError('Posición inválida')
    if board.is_checkmate():return -2000.0 if board.turn else 2000.0
    if board.is_stalemate() or board.is_insufficient_material():return 0.0
    phase=material_phase(board)
    val=(_one_side(board,True,p,phase,1-phase)-_one_side(board,False,p,phase,1-phase))*p['CALIBRATION_SCALE']/100.0
    if tactical:
        # The player to move has mate in one: explicit urgent tactical score.
        for mv in board.legal_moves:
            board.push(mv)
            checkmate=board.is_checkmate()
            board.pop()
            if checkmate:return 2000.0 if board.turn else -2000.0
    return max(-2000.0,min(2000.0,val))
