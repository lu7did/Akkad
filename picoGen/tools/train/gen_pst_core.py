"""PST: David et al., 35 coefficients, and entrenar_david_ga.py reference.

The paper specifies the terms but not the complete feature formulas. The 11
features absent from the supplied example have explicit conventional chess
definitions documented in picoGenus/docs/README_PST_35_v0.1.15.md.
The remaining 23 evolved terms are unchanged from the supplied example.
Version v0.1.16 refines only three pre-existing detectors with details
implemented in ChessGP, without adding parameters or changing GA fitness.
"""
import numpy as np
import chess

PARAM_SPECS = [
    ("KNIGHT_VALUE", 11), ("BISHOP_VALUE", 11), ("ROOK_VALUE", 11), ("QUEEN_VALUE", 11),
    ("PAWN_ADVANCE_A", 6), ("PAWN_ADVANCE_B", 6), ("PASSED_PAWN_MULT", 6),
    ("DOUBLED_PAWN_PENALTY", 6), ("ISOLATED_PAWN_PENALTY", 6), ("BACKWARD_PAWN_PENALTY", 6),
    ("WEAK_SQUARE_PENALTY", 6), ("PASSED_PAWN_ENEMY_KING_DIST", 6),
    ("KNIGHT_SQ_MULT", 6), ("KNIGHT_OUTPOST_MULT", 6),
    ("BISHOP_MOBILITY", 6), ("BISHOP_PAIR", 6),
    ("ROOK_ATTACK_KING_FILE", 6), ("ROOK_ATTACK_KING_ADJ_FILE", 6),
    ("ROOK_ATTACK_KING_ADJ_FILE_ABGH", 6), ("ROOK_7TH_RANK", 6),
    ("ROOK_CONNECTED", 6), ("ROOK_MOBILITY", 6), ("ROOK_BEHIND_PASSED_PAWN", 6),
    ("ROOK_OPEN_FILE", 6), ("ROOK_SEMI_OPEN_FILE", 6),
    ("ROOK_ATCK_WEAK_PAWN_OPEN_COLUMN", 6), ("ROOK_COLUMN_MULT", 6),
    ("QUEEN_MOBILITY", 6),
    ("KING_NO_FRIENDLY_PAWN", 6), ("KING_NO_FRIENDLY_PAWN_ADJ", 6),
    ("KING_FRIENDLY_PAWN_ADVANCED1", 6), ("KING_NO_ENEMY_PAWN", 6),
    ("KING_NO_ENEMY_PAWN_ADJ", 6), ("KING_PRESSURE_MULT", 6)
]

BITS = 224
NAMES = [name for name, _ in PARAM_SPECS]
assert len(PARAM_SPECS) == 34 and sum(b for _,b in PARAM_SPECS) == BITS

def gray_a_binario(gray_bits):
    bin_bits = np.zeros_like(gray_bits)
    bin_bits[0] = gray_bits[0]
    for i in range(1, len(gray_bits)):
        bin_bits[i] = bin_bits[i - 1] ^ gray_bits[i]
    valor = 0
    for bit in bin_bits:
        valor = (valor << 1) | int(bit)
    return valor

def decodificar_cromosoma(cromosoma_bits):
    params = {"PAWN_VALUE": 100}
    idx = 0
    for nombre, num_bits in PARAM_SPECS:
        segmento = cromosoma_bits[idx : idx + num_bits]
        params[nombre] = gray_a_binario(segmento)
        idx += num_bits
    return params

def _passed_pawn(board, square, color):
    """No enemy pawn may be ahead on same or adjacent file."""
    f, r = chess.square_file(square), chess.square_rank(square)
    for other in board.pieces(chess.PAWN, not color):
        if abs(chess.square_file(other) - f) <= 1:
            other_r = chess.square_rank(other)
            if (other_r > r) if color == chess.WHITE else (other_r < r):
                return False
    return True


def _backward_pawn(board, square, color):
    """Unsupported pawn, unable to advance safely because of enemy pawn control."""
    f, r = chess.square_file(square), chess.square_rank(square)
    direction = 1 if color == chess.WHITE else -1
    next_rank = r + direction
    if not 0 <= next_rank <= 7:
        return False
    # A neighbouring friendly pawn on same rank or further back can support
    # the pawn's advance (a pawn already ahead cannot).
    support = any(
        abs(chess.square_file(other) - f) == 1 and
        ((chess.square_rank(other) <= r) if color == chess.WHITE
         else (chess.square_rank(other) >= r))
        for other in board.pieces(chess.PAWN, color)
    )
    if support:
        return False
    next_square = chess.square(f, next_rank)
    # ChessGP IsBackwardPawn: only a clear front square qualifies.
    # An occupied square must not receive this penalty under this detector.
    if board.piece_at(next_square) is not None:
        return False
    # An enemy pawn controls the square immediately ahead.
    return any(next_square in board.attacks(other)
               for other in board.pieces(chess.PAWN, not color))


def _weak_squares(board, color):
    """Central squares in own half controlled by opponent but not own pawns."""
    own_pawn_attacks = set()
    for square in board.pieces(chess.PAWN, color):
        own_pawn_attacks.update(board.attacks(square))
    enemy_attacks = set()
    for square, piece in board.piece_map().items():
        if piece.color != color:
            enemy_attacks.update(board.attacks(square))
    own_half = range(0, 4) if color == chess.WHITE else range(4, 8)
    return sum(chess.square(f, r) in enemy_attacks and
               chess.square(f, r) not in own_pawn_attacks
               for r in own_half for f in (2, 3, 4, 5))


def _connected_rooks(board, rooks):
    squares = list(rooks)
    for a_index, a in enumerate(squares):
        for b in squares[a_index+1:]:
            if (chess.square_rank(a) == chess.square_rank(b) or
                chess.square_file(a) == chess.square_file(b)):
                if not (chess.between(a, b) & board.occupied):
                    return True
    return False


def _clear_file_between(board, square_a, square_b):
    """ChessGP ClearFileLine: same file, with no intervening pieces.

    Only intervening squares matter: the endpoints may contain rook/pawn.
    """
    if chess.square_file(square_a) != chess.square_file(square_b):
        return False
    return not bool(chess.between(square_a, square_b) & board.occupied)


def _king_pressure(board, attacker, defender_king):
    """Attacks by non-king pieces on king square and adjacent squares."""
    ring = set(chess.SquareSet(chess.BB_KING_ATTACKS[defender_king]))
    ring.add(defender_king)
    return sum(len(ring.intersection(board.attacks(sq)))
               for sq, piece in board.piece_map().items()
               if piece.color == attacker and piece.piece_type != chess.KING)


def evaluar_posicion_david(board: chess.Board, p: dict) -> int:
    if board.is_checkmate():
        return -99999 if board.turn == chess.WHITE else 99999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for color in (chess.WHITE, chess.BLACK):
        signo = 1 if color == chess.WHITE else -1
        enemigo = not color

        peones = board.pieces(chess.PAWN, color)
        caballos = board.pieces(chess.KNIGHT, color)
        alfiles = board.pieces(chess.BISHOP, color)
        torres = board.pieces(chess.ROOK, color)
        damas = board.pieces(chess.QUEEN, color)
        rey_sq = board.king(color)
        rey_enemigo_sq = board.king(enemigo)

        peones_enemigos = board.pieces(chess.PAWN, enemigo)

        # --- Material ---
        mat = (
            len(peones) * p["PAWN_VALUE"]
            + len(caballos) * p["KNIGHT_VALUE"]
            + len(alfiles) * p["BISHOP_VALUE"]
            + len(torres) * p["ROOK_VALUE"]
            + len(damas) * p["QUEEN_VALUE"]
        )
        if len(alfiles) >= 2:
            mat += p["BISHOP_PAIR"]
        score += signo * mat

        # --- Estructura de Peones ---
        archivos_peones = [chess.square_file(sq) for sq in peones]
        for sq in peones:
            f = chess.square_file(sq)
            r = chess.square_rank(sq)
            avance = r if color == chess.WHITE else (7 - r)

            # Bonificación por avance de peón
            score += signo * (avance * p["PAWN_ADVANCE_A"] + (avance // 2) * p["PAWN_ADVANCE_B"])

            # Peones doblados y aislados
            if archivos_peones.count(f) > 1:
                score -= signo * p["DOUBLED_PAWN_PENALTY"]
            tiene_vecino = any(abs(af - f) == 1 for af in archivos_peones)
            if not tiene_vecino:
                score -= signo * p["ISOLATED_PAWN_PENALTY"]

            # Peón pasado (sin peones enemigos delante en columnas f-1, f, f+1)
            es_pasado = True
            for esq in peones_enemigos:
                ef = chess.square_file(esq)
                er = chess.square_rank(esq)
                if abs(ef - f) <= 1:
                    if (color == chess.WHITE and er > r) or (color == chess.BLACK and er < r):
                        es_pasado = False
                        break
            if es_pasado:
                dist_rey_enemigo = chess.square_distance(sq, rey_enemigo_sq)
                score += signo * (avance * p["PASSED_PAWN_MULT"] + dist_rey_enemigo * p["PASSED_PAWN_ENEMY_KING_DIST"])

        # --- David: backward pawn and weak square penalty ---
        score -= signo * sum(_backward_pawn(board, sq, color) for sq in peones) * p["BACKWARD_PAWN_PENALTY"]
        score -= signo * _weak_squares(board, color) * p["WEAK_SQUARE_PENALTY"]

        # --- Caballos (Centralización y Outposts) ---
        for sq in caballos:
            f, r = chess.square_file(sq), chess.square_rank(sq)
            centralidad = (3.5 - abs(3.5 - f)) + (3.5 - abs(3.5 - r))
            score += signo * int(centralidad * p["KNIGHT_SQ_MULT"])
            if (color == chess.WHITE and r >= 4) or (color == chess.BLACK and r <= 3):
                score += signo * p["KNIGHT_OUTPOST_MULT"]

        # --- Alfiles (Movilidad) ---
        for sq in alfiles:
            movilidad = len(board.attacks(sq))
            score += signo * (movilidad * p["BISHOP_MOBILITY"])

        # --- David: connected rooks ---
        if _connected_rooks(board, torres):
            score += signo * p["ROOK_CONNECTED"]

        # --- Torres (Columnas abiertas, 7ª fila, movilidad, ataque al rey) ---
        rey_en_f = chess.square_file(rey_enemigo_sq)
        for sq in torres:
            f, r = chess.square_file(sq), chess.square_rank(sq)
            movilidad = len(board.attacks(sq))
            score += signo * (movilidad * p["ROOK_MOBILITY"])

            if (color == chess.WHITE and r == 6) or (color == chess.BLACK and r == 1):
                score += signo * p["ROOK_7TH_RANK"]

            peones_propios_col = sum(1 for psq in peones if chess.square_file(psq) == f)
            peones_enem_col = sum(1 for psq in peones_enemigos if chess.square_file(psq) == f)
            if peones_propios_col == 0 and peones_enem_col == 0:
                score += signo * p["ROOK_OPEN_FILE"]
            elif peones_propios_col == 0:
                score += signo * p["ROOK_SEMI_OPEN_FILE"]

            if f == rey_en_f:
                score += signo * p["ROOK_ATTACK_KING_FILE"]
            elif abs(f - rey_en_f) == 1:
                score += signo * p["ROOK_ATTACK_KING_ADJ_FILE"]
                if rey_en_f in (0, 1, 6, 7):
                    score += signo * p["ROOK_ATTACK_KING_ADJ_FILE_ABGH"]

            # Rook behind a friendly passed pawn on the same file.
            if any(chess.square_file(pawn) == f and
                   ((chess.square_rank(pawn) > r) if color == chess.WHITE
                    else (chess.square_rank(pawn) < r)) and
                   _passed_pawn(board, pawn, color) and
                   _clear_file_between(board, sq, pawn)
                   for pawn in peones):
                score += signo * p["ROOK_BEHIND_PASSED_PAWN"]

            # Open / semi-open rook files: additional file multiplier,
            # and pressure on a weak opponent pawn when our file is open.
            if peones_propios_col == 0:
                score += signo * p["ROOK_COLUMN_MULT"] * (2 if peones_enem_col == 0 else 1)
                if any(chess.square_file(ep) == f and
                       _clear_file_between(board, sq, ep) and
                       (_backward_pawn(board, ep, enemigo) or
                        not any(abs(chess.square_file(other)-f) == 1
                                for other in peones_enemigos))
                       for ep in peones_enemigos):
                    score += signo * p["ROOK_ATCK_WEAK_PAWN_OPEN_COLUMN"]

        # --- Damas (Movilidad) ---
        for sq in damas:
            score += signo * (len(board.attacks(sq)) * p["QUEEN_MOBILITY"])

        # --- Seguridad del Rey ---
        rf = chess.square_file(rey_sq)
        rr = chess.square_rank(rey_sq)
        fila_escudo = rr + 1 if color == chess.WHITE else rr - 1
        if 0 <= fila_escudo <= 7:
            for df in (-1, 0, 1):
                cf = rf + df
                if 0 <= cf <= 7:
                    sq_escudo = chess.square(cf, fila_escudo)
                    pieza_escudo = board.piece_at(sq_escudo)
                    if not pieza_escudo or pieza_escudo.piece_type != chess.PAWN or pieza_escudo.color != color:
                        pen = p["KING_NO_FRIENDLY_PAWN"] if df == 0 else p["KING_NO_FRIENDLY_PAWN_ADJ"]
                        score -= signo * pen

        # David: advanced friendly pawn shield (two ranks in front of king).
        advanced_rank = rr + (2 if color == chess.WHITE else -2)
        if 0 <= advanced_rank <= 7:
            for df in (-1, 0, 1):
                if 0 <= rf + df <= 7:
                    piece = board.piece_at(chess.square(rf + df, advanced_rank))
                    if piece and piece.piece_type == chess.PAWN and piece.color == color:
                        score += signo * p["KING_FRIENDLY_PAWN_ADVANCED1"]

        # Enemy pawn absence on king file and adjacent files.
        enemy_pawn_files = {chess.square_file(sq) for sq in peones_enemigos}
        if rf not in enemy_pawn_files:
            score -= signo * p["KING_NO_ENEMY_PAWN"]
        for df in (-1, 1):
            if 0 <= rf + df <= 7 and (rf + df) not in enemy_pawn_files:
                score -= signo * p["KING_NO_ENEMY_PAWN_ADJ"]

        # Own attacking pressure near the opposing king.
        score += signo * p["KING_PRESSURE_MULT"] * _king_pressure(board, color, rey_enemigo_sq)

    return score

def elegir_jugada_1ply(board: chess.Board, params: dict) -> chess.Move:
    mejor_mov = None
    es_blanco = (board.turn == chess.WHITE)
    mejor_val = -999999 if es_blanco else 999999

    for mov in board.legal_moves:
        board.push(mov)
        val = evaluar_posicion_david(board, params)
        board.pop()
        if (es_blanco and val > mejor_val) or (not es_blanco and val < mejor_val):
            mejor_val = val
            mejor_mov = mov
    return mejor_mov


def decode(chromosomes):
    """Puente de formato; decodificación Gray por el algoritmo del ejemplo."""
    bits=np.asarray(chromosomes,dtype=np.uint8)
    if bits.ndim==1:bits=bits[None,:]
    if bits.ndim!=2 or bits.shape[1]!=BITS or np.any(bits>1):
        raise ValueError('Se requieren 224 bits binarios por cromosoma')
    return np.asarray([[decodificar_cromosoma(row)[name] for name in NAMES] for row in bits],dtype=np.float64)


def encode_values(values):
    """Representación Gray de valores, para pruebas de ida y vuelta."""
    if len(values)!=len(PARAM_SPECS):raise ValueError('Cantidad de parámetros incorrecta')
    bits=[]
    for value,(_,width) in zip(values,PARAM_SPECS):
        if int(value)!=value or not 0<=int(value)<(1<<width):
            raise ValueError('Parámetro fuera de rango')
        gray=int(value)^(int(value)>>1)
        bits.extend((gray>>k)&1 for k in range(width-1,-1,-1))
    return np.asarray(bits,dtype=np.uint8)


def evaluate(board,params):
    """Misma función que evaluar_posicion_david; contrato Nurse: CP blancos."""
    if isinstance(params,dict):p=params
    else:
        if len(params)!=len(NAMES):raise ValueError('Se necesitan 34 parámetros')
        p={'PAWN_VALUE':100}
        p.update(zip(NAMES,(int(x) for x in params)))
    return evaluar_posicion_david(board,p)


def choose_move(board,params):
    if not isinstance(params,dict):
        p={'PAWN_VALUE':100}
        p.update(zip(NAMES,(int(x) for x in params)))
    else:p=params
    return elegir_jugada_1ply(board,p)
