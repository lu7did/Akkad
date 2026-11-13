import math
import random

# Mapeo de piezas a índices (0 a 11)
PIECE_IDX = {
    'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5,
    'p': 6, 'n': 7, 'b': 8, 'r': 9, 'q': 10, 'k': 11
}

class AlphaZeroTinyNet:
    def __init__(self, hidden_size=16):
        self.hidden_size = hidden_size
        random.seed(42)

        # 1. Capa de entrada compartida: (12 piezas * 64 casillas = 768) -> hidden_size
        # En la Pico, esto ocupa ~12 KB si se guarda como floats o ~1.5 KB como int8
        self.w_in = [
            [random.uniform(-0.1, 0.1) for _ in range(hidden_size)]
            for _ in range(768)
        ]

        # 2. Cabeza de Valor: hidden_size -> 1 (evalúa quién gana de -1 a 1)
        self.w_value = [random.uniform(-0.1, 0.1) for _ in range(hidden_size)]

        # 3. Cabeza de Política Factorizada: hidden_size -> 64 (origen) + 64 (destino)
        self.w_from = [
            [random.uniform(-0.1, 0.1) for _ in range(64)]
            for _ in range(hidden_size)
        ]
        self.w_to = [
            [random.uniform(-0.1, 0.1) for _ in range(64)]
            for _ in range(hidden_size)
        ]

    def forward(self, board_str, turn, legal_moves):
        """
        Recibe el tablero, el turno (1 o -1) y la lista de movimientos legales [(origen, destino), ...].
        Devuelve: (diccionario_de_politica, valor_del_tablero)
        """
        # --- PASO 1: Capa Oculta (Solo sumamos las piezas presentes en el tablero) ---
        hidden = [0.0] * self.hidden_size
        sq_64 = 0

        for ch in board_str:
            if ch in (' ', '\n'):
                continue
            if ch != '.':
                # Si es turno de negras (-1), invertimos la perspectiva del tablero y color
                if turn == 1:
                    p_idx = PIECE_IDX[ch]
                    sq = sq_64
                else:
                    p_idx = PIECE_IDX[ch.swapcase()]
                    sq = 63 - sq_64

                feature_idx = p_idx * 64 + sq
                weights = self.w_in[feature_idx]
                for h in range(self.hidden_size):
                    hidden[h] += weights[h]
            sq_64 += 1

        # Activación ReLU (mantiene solo valores positivos)
        for h in range(self.hidden_size):
            if hidden[h] < 0.0:
                hidden[h] = 0.0

        # --- PASO 2: Cabeza de Valor ---
        raw_val = 0.0
        for h in range(self.hidden_size):
            raw_val += hidden[h] * self.w_value[h]
        value = math.tanh(raw_val)

        # --- PASO 3: Cabeza de Política (Solo para movimientos legales) ---
        if not legal_moves:
            return {}, value

        logits = []
        max_logit = -9999.0

        for src_120, dst_120 in legal_moves:
            # Convertir índice de tablero 120 a 64 casillas
            src_64 = self._to_64(src_120)
            dst_64 = self._to_64(dst_120)

            if turn == -1:
                src_64 = 63 - src_64
                dst_64 = 63 - dst_64

            # Sumar puntuación de casilla origen + casilla destino
            score = 0.0
            for h in range(self.hidden_size):
                if hidden[h] > 0.0:
                    score += hidden[h] * (self.w_from[h][src_64] + self.w_to[h][dst_64])

            logits.append(score)
            if score > max_logit:
                max_logit = score

        # Softmax numérico estable para convertir puntuaciones en probabilidades
        exp_scores = [math.exp(l - max_logit) for l in logits]
        sum_exp = sum(exp_scores)

        policy = {}
        for i, move in enumerate(legal_moves):
            policy[move] = exp_scores[i] / sum_exp

        return policy, value

    def _to_64(self, idx_120):
        # Convierte índice del formato 10x12 (fil 2..9, col 1..8) a 0..63
        row = (idx_120 // 10) - 2
        col = (idx_120 % 10) - 1
        return row * 8 + col

