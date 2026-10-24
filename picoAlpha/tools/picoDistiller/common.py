"""Shared PB/board utilities. The original Sargon SQLite data is not re-encoded."""
import sqlite3
from pathlib import Path
import numpy as np
import chess

POLICY_SIZE = 4672
SOURCE = 'pico_tinygyal_compatible_112_1x8_v3'

def database(path):
    p=Path(path).expanduser().resolve()
    if not p.is_file() or p.open('rb').read(16)!=b'SQLite format 3\0':
        raise ValueError(f'Not a Sargon SQLite .pb: {p}')
    db=sqlite3.connect(str(p),timeout=30)
    db.execute('PRAGMA foreign_keys=ON')
    fields={r[1] for r in db.execute('PRAGMA table_info(positions)')}
    if not {'id','game_id','ply','features','halfmove'}.issubset(fields):
        raise ValueError('Incompatible positions schema')
    if db.execute('SELECT value FROM meta WHERE key="format"').fetchone() != ('SARGON-PB-SQLITE-1',):
        raise ValueError('Not a Sargon .pb dataset')
    return db

def from_features(blob,halfmove,ply):
    if len(blob)!=98: raise ValueError('Expected 98-byte Sargon features')
    bits=np.unpackbits(np.frombuffer(blob,dtype=np.uint8),bitorder='little')[:781]
    board=chess.Board(None)
    for i in np.flatnonzero(bits[:768]):
        sq,kind=divmod(int(i),12)
        board.set_piece_at(sq,chess.Piece(kind%6+1,kind<6))
    board.turn=bool(bits[780])
    castling=''.join(c for i,c in zip(range(768,772),'KQkq') if bits[i])
    board.set_castling_fen(castling or '-')
    ep=np.flatnonzero(bits[772:780])
    if len(ep)>1:raise ValueError('Multiple en-passant files')
    board.ep_square=chess.square(int(ep[0]),5 if board.turn else 2) if len(ep) else None
    board.halfmove_clock=int(halfmove)
    board.fullmove_number=max(1,int(ply)//2+1)
    if not board.is_valid():raise ValueError(f'Invalid reconstructed board {board.fen()} status={board.status()}')
    return board

def planes(history):
    """Exact planar conventions in picoAlpha/src/net.cpp encode_into (112x64).

    The 8 historical slices are side-to-move relative with vertical rotation
    for Black. Auxiliary planes follow the firmware's existing representation.
    """
    if not history: raise ValueError('Empty history')
    current=history[-1]
    out=np.zeros((112,8,8),dtype=np.float32)
    types=(chess.PAWN,chess.KNIGHT,chess.BISHOP,chess.ROOK,chess.QUEEN,chess.KING)
    for age in range(min(8,len(history))):
        old=history[-1-age]
        for j,ptype in enumerate(types):
            for col,offset in ((current.turn,0),(not current.turn,6)):
                for square in old.pieces(ptype,col):
                    rank=chess.square_rank(square)
                    if current.turn==chess.BLACK: rank=7-rank
                    out[age*13+offset+j,rank,chess.square_file(square)]=1.
        # Approximate firmware's repeated flag with full game history.
        if sum(x._transposition_key()==old._transposition_key() for x in history[:len(history)-age])>=2:
            out[age*13+12,:,:]=1.
    for index,col,kingside in [(104,current.turn,True),(105,current.turn,False),
                               (106,not current.turn,True),(107,not current.turn,False)]:
        if current.has_kingside_castling_rights(col) if kingside else current.has_queenside_castling_rights(col):
            out[index,:,:]=1.
    if current.turn==chess.BLACK: out[108,:,:]=1.
    out[109,:,:]=float(current.halfmove_clock)
    out[111,:,:]=1.
    return out

RAYS=((0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1),(-1,0),(-1,1))
KNIGHTS=((1,2),(2,1),(2,-1),(1,-2),(-1,-2),(-2,-1),(-2,1),(-1,2))

def policy_index(board,move):
    """Exact plane/slot convention of picoAlpha::policy_index in src/net.cpp."""
    fr,to=move.from_square,move.to_square
    if board.is_castling(move):
        to=chess.square(7 if board.is_kingside_castling(move) else 0,chess.square_rank(fr))
    fx,fy=chess.square_file(fr),chess.square_rank(fr)
    tx,ty=chess.square_file(to),chess.square_rank(to)
    if board.turn==chess.BLACK: fy=7-fy;ty=7-ty
    dx,dy=tx-fx,ty-fy
    if move.promotion in (chess.ROOK,chess.BISHOP,chess.KNIGHT):
        if dy!=1 or abs(dx)>1: raise ValueError('Invalid promotion')
        plane=64+(dx+1)*3+{chess.ROOK:0,chess.BISHOP:1,chess.KNIGHT:2}[move.promotion]
    elif (dx,dy) in KNIGHTS: plane=56+KNIGHTS.index((dx,dy))
    else:
        steps=max(abs(dx),abs(dy))
        if not 1<=steps<=7: raise ValueError('Invalid ray')
        direction=((dx>0)-(dx<0),(dy>0)-(dy<0))
        if direction not in RAYS: raise ValueError('Invalid direction')
        plane=RAYS.index(direction)*7+steps-1
    return plane*64+fy*8+fx


def reconstruct_game(rows):
    """Yield (position_id, history) for contiguous games starting at ply 0 or 1.

    Sargon PGN imports may store the initial position (ply 0) or the board
    immediately after White's first move (ply 1). In the latter case recover
    the actual first legal move from the standard start position, so that the
    move stack sent to LC0 is complete. Never fabricate missing plies.
    """
    history = []
    previous = None
    last_ply = None

    def unique_transition(before, after, ply):
        found = []
        target = after.fen()
        for move in before.legal_moves:
            trial = before.copy(stack=False)
            trial.push(move)
            if trial.fen() == target:
                found.append(move)
        if len(found) != 1:
            raise ValueError(f'Expected one legal transition at ply {ply}; got {len(found)}')
        return found[0]

    for position_id, ply, features, halfmove in rows:
        current = from_features(features, halfmove, ply)
        if previous is None:
            start = chess.Board()
            if ply == 0:
                if current.fen() != start.fen():
                    raise ValueError('First ply 0 board does not match chess start position')
                previous = start
                history.append(start.copy(stack=True))
                last_ply = 0
                yield position_id, history[:]
                continue
            if ply != 1:
                raise ValueError(f'Game begins at ply {ply}; missing opening moves')
            first_move = unique_transition(start, current, ply)
            start.push(first_move)
            previous = start
            history.extend((chess.Board(), start.copy(stack=True)))
        else:
            if ply != last_ply + 1:
                raise ValueError(f'Nonconsecutive positions: {last_ply} -> {ply}')
            move = unique_transition(previous, current, ply)
            previous.push(move)
            history.append(previous.copy(stack=True))
        last_ply = ply
        yield position_id, history[:]

def progress(label,n,total,extra=''):
    f=n/max(1,total); k=round(25*f)
    print(f'\r{label:12s} {n:8d}/{total:<8d} '+ '█'*k+'░'*(25-k)+f' {f*100:5.1f}% {extra:35s}',end='',flush=True)
    if n==total: print()
