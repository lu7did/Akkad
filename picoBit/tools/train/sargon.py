"""Algoritmo Sargon aportado por el usuario el 19-11-2026.
Transcripción funcional sin cambios de constantes ni heurísticas.
Escala: puntos Sargon (NO centipeones). POV: blancas.
"""
import chess

PIECE_VALUES = {
    chess.PAWN: 16,
    chess.KNIGHT: 48,
    chess.BISHOP: 48,
    chess.ROOK: 80,
    chess.QUEEN: 144,
    chess.KING: 0,
}

CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.F4, chess.C5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}


def static_exchange_evaluation(board: chess.Board, square: chess.Square) -> int:
    """Simula la rutina de resolución de batallas de Sargon en una casilla.
    Calcula la ganancia o pérdida neta de material si se inician capturas en `square`.
    """
    target_piece = board.piece_at(square)
    if not target_piece:
        return 0

    white_attackers = sorted(
        [board.piece_type_at(sq) for sq in board.attackers(chess.WHITE, square)],
        key=lambda pt: PIECE_VALUES[pt],
    )
    black_attackers = sorted(
        [board.piece_type_at(sq) for sq in board.attackers(chess.BLACK, square)],
        key=lambda pt: PIECE_VALUES[pt],
    )

    gains = []
    side = board.turn
    current_piece_val = PIECE_VALUES[target_piece.piece_type]

    while True:
        attackers = white_attackers if side == chess.WHITE else black_attackers
        if not attackers:
            break
        gains.append(current_piece_val)
        attacker_type = attackers.pop(0)
        current_piece_val = PIECE_VALUES[attacker_type]
        side = not side

    for i in range(len(gains) - 2, -1, -1):
        gains[i] = max(0, gains[i] - gains[i + 1])

    if not gains:
        return 0
    return gains[0] if board.turn == chess.WHITE else -gains[0]


def evaluate_sargon(board: chess.Board) -> int:
    """Función estática tipo POINTS de Sargon (1978), POV blancas, puntos Sargon."""
    if board.is_checkmate():
        return -9999 if board.turn == chess.WHITE else 9999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for square, piece in board.piece_map().items():
        val = PIECE_VALUES[piece.piece_type]
        sign = 1 if piece.color == chess.WHITE else -1
        score += sign * val

        rank = chess.square_rank(square)
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            if (piece.color == chess.WHITE and rank == 0) or (piece.color == chess.BLACK and rank == 7):
                score -= sign * 2

        if piece.piece_type == chess.KING:
            file = chess.square_file(square)
            if (piece.color == chess.WHITE and rank == 0 and file in (2, 6)) or \
               (piece.color == chess.BLACK and rank == 7 and file in (2, 6)):
                score += sign * 6

    for sq in chess.SQUARES:
        w_attacks = len(board.attackers(chess.WHITE, sq))
        b_attacks = len(board.attackers(chess.BLACK, sq))

        weight = 1
        if sq in CENTER_SQUARES:
            weight = 3
        elif sq in EXTENDED_CENTER:
            weight = 2

        score += (w_attacks - b_attacks) * weight

    exchange_scores = []
    for sq, piece in board.piece_map().items():
        if piece.color != board.turn:
            if board.is_attacked_by(board.turn, sq):
                see = static_exchange_evaluation(board, sq)
                if (board.turn == chess.WHITE and see > 0) or (board.turn == chess.BLACK and see < 0):
                    exchange_scores.append(see)

    if exchange_scores:
        score += max(exchange_scores) if board.turn == chess.WHITE else min(exchange_scores)

    return score


if __name__ == "__main__":
    tablero = chess.Board()
    print(f"Evaluación posición inicial: {evaluate_sargon(tablero)}")
    tablero.push_san("e4")
    print(f"Evaluación tras 1. e4: {evaluate_sargon(tablero)}")
