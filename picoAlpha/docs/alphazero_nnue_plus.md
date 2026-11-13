En la versión minimalista anterior (768 entradas) se omitieron intencionalmente el enroque, la captura al paso y el reloj de 50 jugadas para mantener el motor en menos de 150 líneas y ahorrar cada byte de RAM en la Raspberry Pi Pico.
Sin embargo, añadir esos elementos a la red neuronal y al motor es muy sencillo y casi no consume memoria extra.

1. ¿Cómo representarlos en la Red Neuronal?

En lugar de tener 768 entradas (12 piezas × 64 casillas), ampliamos el vector de entrada a 780 entradas (solo 12 filas extra en la matriz W_IN, lo que suma menos de 200 bytes):
• Índices 0 a 767: Las 12 piezas en las 64 casillas (igual que antes).
• Índices 768 a 771 (4 entradas - Derechos de enroque):
	• 768: El jugador activo puede enrocar corto (O-O).
	• 769: El jugador activo puede enrocar largo (O-O-O).
	• 770: El rival puede enrocar corto.
	• 771: El rival puede enrocar largo.
• Índices 772 a 779 (8 entradas - Captura al paso / En Passant):
	• Representan las 8 columnas (a hasta h, ajustadas a la perspectiva del jugador activo). Si el rival acaba de avanzar un peón dos pasos en la columna e, se activa el índice correspondiente a esa columna.
(Nota: El turno ya está implícito porque siempre giramos el tablero hacia el jugador activo, y el regla de las 50 jugadas / repetición suele manejarse directamente en el árbol MCTS devolviendo 0.0 de empate, sin gastar neuronas).

2. ¿Cómo cambiar el código en PyTorch?

Solo tienes que actualizar el tamaño de EmbeddingBag de 768 a 780 y agregar las condiciones en board_to_features:
python
class AlphaZeroTinyNetTorch(nn.Module):
    def __init__(self, hidden_size=16):
        super().__init__()
        # Aumentamos de 768 a 780 entradas (+12 características de estado)
        self.embed = nn.EmbeddingBag(780, hidden_size, mode='sum')
        self.val_head = nn.Linear(hidden_size, 1, bias=False)
        self.from_head = nn.Linear(hidden_size, 64, bias=False)
        self.to_head = nn.Linear(hidden_size, 64, bias=False)
    # ... el resto de la clase queda igual ...

def board_to_features(board):
    indices = []
    turn = board.turn

    # 1. Piezas en el tablero (0..767)
    for sq, piece in board.piece_map().items():
        symbol = piece.symbol()
        if turn == chess.WHITE:
            p_idx = PIECE_MAP[symbol]
            sq_flipped = (7 - (sq // 8)) * 8 + (sq % 8)
        else:
            p_idx = PIECE_MAP[symbol.swapcase()]
            sq_flipped = 63 - ((7 - (sq // 8)) * 8 + (sq % 8))
        indices.append(p_idx * 64 + sq_flipped)

    # 2. Derechos de enroque (768..771) desde perspectiva del turno
    rival = not turn
    if board.has_kingside_castling_rights(turn):   indices.append(768)
    if board.has_queenside_castling_rights(turn):  indices.append(769)
    if board.has_kingside_castling_rights(rival):  indices.append(770)
    if board.has_queenside_castling_rights(rival): indices.append(771)

    # 3. Captura al paso / En Passant (772..779)
    if board.ep_square is not None:
        ep_col = chess.square_file(board.ep_square)
        if turn == chess.BLACK:
            ep_col = 7 - ep_col # Invertir columna si juegan negras
        indices.append(772 + ep_col)

    return indices
Usa el código con precaución.

3. Impacto en el motor de la Raspberry Pi Pico

Para que esto funcione en la Pico, el estado del juego (MicroChess) también debe guardar una tupla ligera de 4 elementos (enroques, casilla_ep) y aplicar las reglas en generate_moves():
• Enroque: Verificar que el rey y la torre no se hayan movido, que no haya piezas entre ellos y que el rey no pase por casillas atacadas.
• Al paso (ep_square): Si un peón avanza 2 casillas, guardar la casilla intermedia en ep_square para el siguiente turno (y borrarla si no se usa).
• Repetición de jugadas: En el MCTS, guardar un historial simple de los tableros visitados en la rama actual; si una posición se repite, el nodo devuelve valor 0.0 (tablas) para evitar bucles infinitos.
¿Quieres que actualicemos la clase MicroChess de la Raspberry Pi Pico para que incluya el soporte completo de enroque, captura al paso y lectura de las 780 entradas?

