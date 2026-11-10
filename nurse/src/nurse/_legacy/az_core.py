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
#* az_core.py
#* AlphaZero experiment version 0.6.114: chess action encoding and PB state helpers.
#* v0.6.153
#=================================================================================================================*
"""AlphaZero experiment v0.6.114: chess action encoding and PB state helpers.

No changes to the legacy Sargon input encoder or data schema.
"""
from __future__ import annotations
import math
import chess
import numpy as np
from .pb_data import pack, unpack
from .evaluators.npz import INPUT_SIZE, NpzEvaluator

VERSION = '0.6.116'
ACTION_SIZE = 64 * 73
DIRECTIONS = ((0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1),(-1,0),(-1,1))
KNIGHTS = ((1,2),(2,1),(2,-1),(1,-2),(-1,-2),(-2,-1),(-2,1),(-1,2))
ENCODER = NpzEvaluator.__new__(NpzEvaluator)


def action_id(board: chess.Board, move: chess.Move) -> int:
    """Canonical absolute-square 8x8x73 action space; preserves promotions."""
    if move not in board.legal_moves:
        raise ValueError(f'Movimiento ilegal {move.uci()} en {board.fen()}')
    fx, fy = chess.square_file(move.from_square), chess.square_rank(move.from_square)
    tx, ty = chess.square_file(move.to_square), chess.square_rank(move.to_square)
    dx, dy = tx-fx, ty-fy
    if move.promotion in (chess.KNIGHT, chess.BISHOP, chess.ROOK):
        if (1 if board.turn else -1) != dy or dx not in (-1,0,1):
            raise ValueError('Promocion menor incompatible')
        plane = 64 + (move.promotion-chess.KNIGHT)*3 + (dx+1)
    elif (dx,dy) in KNIGHTS:
        plane = 56 + KNIGHTS.index((dx,dy))
    else:
        distance = max(abs(dx),abs(dy))
        if distance < 1 or distance > 7:
            raise ValueError('Desplazamiento fuera del catalogo AlphaZero')
        step = (dx // distance, dy // distance)
        if step not in DIRECTIONS:
            raise ValueError('Direccion invalida')
        plane = DIRECTIONS.index(step)*7 + distance-1
    return move.from_square*73+plane


def legal_action_ids(board: chess.Board) -> list[int]:
    ids = [action_id(board,m) for m in board.legal_moves]
    if len(ids)!=len(set(ids)):
        raise ValueError('Colision en el catalogo de acciones; revisar codificacion')
    return ids


def features(board: chess.Board) -> bytes:
    return pack(board, ENCODER)


def reconstruct(blob: bytes, halfmove: int, ply: int, side: str | None = None) -> chess.Board:
    """Rebuild what the PB can represent, without inventing repetition history."""
    active = set(map(int, unpack(blob)))
    board = chess.Board(None)
    for index in active:
        if index < 768:
            square, kind = divmod(index,12)
            board.set_piece_at(square, chess.Piece(kind%6+1, kind<6))
    board.turn = 780 in active
    rights = ''.join(c for i,c in ((768,'K'),(769,'Q'),(770,'k'),(771,'q')) if i in active)
    board.set_castling_fen(rights or '-')
    ep = sorted(i-772 for i in active if 772<=i<780)
    if len(ep)>1: raise ValueError('Multiples en-passant')
    board.ep_square = chess.square(ep[0],5 if board.turn else 2) if ep else None
    board.halfmove_clock = int(halfmove)
    board.fullmove_number = (int(ply)+2)//2
    if side is not None and board.turn == (side=='W'):
        raise ValueError('PB.side incompatible con jugador al turno')
    if not board.is_valid() or features(board)!=blob:
        raise ValueError('Posicion historica corrupta o no reconstruible')
    return board


def find_transition(board: chess.Board, next_blob: bytes, next_halfmove: int) -> chess.Move:
    found=[]
    for move in board.legal_moves:
        board.push(move)
        match = (board.halfmove_clock==next_halfmove and features(board)==next_blob)
        board.pop()
        if match: found.append(move)
    if len(found)!=1:
        raise ValueError(f'Transicion historica ambigua/invalida: {len(found)} jugadas')
    return found[0]


def value_white(result: int, row: dict, weights: tuple[float,float,float], *, use_smoothed: bool) -> float:
    """All sources are transformed to white-perspective [0,1]. Strict missing labels."""
    sw,cw,rw = weights
    parts=[]
    if sw:
        sf=row.get('stockfish_value')
        if sf is None and row.get('wdl_source') in ('STOCKFISH','TERMINAL'):
            sf=(row['w']+row['d']/2)/1000.0
        if sf is None: raise ValueError('Falta etiqueta Stockfish solicitada')
        parts.append(sw*float(sf))
    if cw:
        cp=row.get('classic_cp')
        if cp is None: raise ValueError('Falta etiqueta CLASSIC solicitada')
        cp=max(-12000.0,min(12000.0,float(cp)))
        parts.append(cw*(1.0/(1.0+math.exp(-cp/400.0))))
    if rw:
        rv=row.get('result_value') if use_smoothed else None
        parts.append(rw*(float(rv) if rv is not None else result/2.0))
    v=sum(parts)
    if not math.isfinite(v) or not 0<=v<=1: raise ValueError('Valor fuera de [0,1]')
    return v


def outcome_target(result: str, white_to_move: bool) -> float:
    values={'1-0':1.0,'0-1':-1.0,'1/2-1/2':0.0}
    if result not in values: raise ValueError(f'Resultado no final: {result!r}')
    return values[result] * (1 if white_to_move else -1)
